#!/usr/bin/env python3
"""Validate the portable Power BI project without pretending to run Desktop.

Install the optional validator dependency with `python -m pip install jsonschema`.
Use --schema-cache to reuse downloaded official schemas. Network schema URLs are
restricted to Microsoft's public schema service. Exit code 0 means all available
schema, structure and data checks passed; it does not prove Desktop rendering,
Power Query execution, DAX evaluation, refresh or PBIX serialization.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import math
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import zlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def walk(value, location=()):
    yield location, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, location + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, location + (index,))


def expr_text(value):
    return '\n'.join(value) if isinstance(value, list) else str(value or '')


class Validation:
    def __init__(self, project: Path):
        self.project = project
        self.checks = []
        self.errors = []
        self.warnings = []
        self.schemas = []
        self.files = []
        self.summary = {}

    def record(self, name, ok, detail):
        self.checks.append({'name': name, 'passed': bool(ok), 'detail': detail})
        if not ok:
            self.errors.append({'check': name, 'detail': detail})

    def relative(self, path):
        try:
            return str(path.relative_to(self.project)).replace('\\', '/')
        except ValueError:
            return path.name

    def load(self, path):
        raw = path.read_bytes()
        data = json.loads(raw)
        self.files.append({'path': self.relative(path), 'sha256': sha256(raw), 'bytes': len(raw)})
        return data

    def resolve(self, base, relative, name):
        good = isinstance(relative, str) and not Path(relative).is_absolute() and '\\' not in relative
        target = (base / relative).resolve() if isinstance(relative, str) else base
        good = good and target.is_relative_to(self.project.resolve()) and target.exists()
        self.record(name, good, {'reference': relative, 'resolved': self.relative(target)})
        return target


class OfficialSchemas:
    """Schema cache keyed by official URL, with optional $id-based seed files."""
    def __init__(self, cache):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.loaded = {}
        self.paths = {}
        for candidate in cache.rglob('*.json'):
            try:
                data = json.loads(candidate.read_text())
                if isinstance(data, dict) and isinstance(data.get('$id'), str):
                    self.loaded[data['$id']] = data
                    self.paths[data['$id']] = candidate
                # Microsoft's downloaded tree includes embedded schemas without $id.
                relative = candidate.relative_to(cache).as_posix()
                if isinstance(data, dict) and relative.startswith('fabric/'):
                    url = 'https://developer.microsoft.com/json-schemas/' + relative
                    self.loaded[url] = data
                    self.paths[url] = candidate
            except (ValueError, OSError):
                pass
        manifest = cache / 'schema_index.json'
        if manifest.exists():
            index = json.loads(manifest.read_text())
            for url, filename in index.items():
                candidate = cache / filename
                if candidate.exists():
                    self.loaded[url] = json.loads(candidate.read_text())
                    self.paths[url] = candidate

    def get(self, url):
        url = urllib.parse.urldefrag(url)[0]
        if url in self.loaded:
            return self.loaded[url]
        parts = urllib.parse.urlparse(url)
        if parts.scheme != 'https' or parts.netloc != 'developer.microsoft.com' or not parts.path.startswith('/json-schemas/'):
            raise ValueError(f'Non-Microsoft schema URL refused: {url}')
        path = self.cache / (sha256(url.encode()) + '.json')
        if path.exists():
            raw = path.read_bytes()
        else:
            request = urllib.request.Request(url, headers={'User-Agent': 'IRCTC-PowerBI-Validator/1.0'})
            raw = urllib.request.urlopen(request, timeout=45).read()
            path.write_bytes(raw)
        data = json.loads(raw)
        self.loaded[url] = data
        self.paths[url] = path
        self.save_index()
        return data

    def save_index(self):
        index = {url: str(path.relative_to(self.cache)) for url, path in self.paths.items()}
        (self.cache / 'schema_index.json').write_text(json.dumps(index, indent=2))


def validate_schema(v, schema_store, path, data, registry, validators):
    url = data.get('$schema') if isinstance(data, dict) else None
    if not url:
        return False
    try:
        schema = schema_store.get(url)
        validator_cls = validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema, registry=registry, format_checker=validator_cls.FORMAT_CHECKER)
        errors = sorted(validator.iter_errors(data), key=lambda e: str(list(e.absolute_path)))
        detail = [{'path': '/'.join(map(str, e.absolute_path)), 'message': e.message[:800]} for e in errors]
        v.record('official_schema:' + v.relative(path), not errors, detail or url)
        v.schemas.append({'file': v.relative(path), 'url': url, 'schema_sha256': sha256(json.dumps(schema, sort_keys=True).encode()), 'validator': validator_cls.__name__, 'passed': not errors})
        return True
    except Exception as exc:
        v.record('official_schema:' + v.relative(path), False, f'{type(exc).__name__}: {exc}')
        return False


def field_references(v, documents, table_columns, table_measures):
    checked = 0
    bad = []
    table_lookup = {name.lower(): name for name in table_columns}
    for path, document in documents:
        aliases = {}
        for _, node in walk(document):
            if isinstance(node, dict) and isinstance(node.get('From'), list):
                aliases.update({x.get('Name'): x.get('Entity') for x in node['From'] if isinstance(x, dict)})
        for loc, node in walk(document):
            if not isinstance(node, dict):
                continue
            for kind, available in [('Column', table_columns), ('Measure', table_measures)]:
                reference = node.get(kind)
                if not isinstance(reference, dict) or 'Property' not in reference:
                    continue
                checked += 1
                source = reference.get('Expression', {}).get('SourceRef', {})
                entity = source.get('Entity') or aliases.get(source.get('Source'))
                prop = reference.get('Property')
                canonical = table_lookup.get(str(entity).lower())
                good = canonical is not None and str(prop).lower() in {x.lower() for x in available.get(canonical, set())}
                if not good:
                    bad.append({'file': v.relative(path), 'path': list(loc), 'kind': kind, 'table': entity, 'property': prop})
    v.record('report_field_references', checked > 0 and not bad, {'references_checked': checked, 'invalid': bad})


def decode_embedded_source(expression):
    """Decode the literal Binary.FromText payload used by the delivered model.

    Accept Deflate/GZip-compressed CSV or JSON; no M evaluation is attempted.
    """
    matches = re.findall(r'Binary\.FromText\(\s*"([A-Za-z0-9+/=\s]+)"\s*,\s*BinaryEncoding\.Base64\s*\)', expression)
    if not matches:
        chunks = re.search(r'EmbeddedBase64\s*=\s*Text\.Combine\(\s*\{(.*?)\}\s*,\s*""\s*\)', expression, re.S)
        if chunks and re.search(r'Binary\.FromText\(\s*EmbeddedBase64\s*,\s*BinaryEncoding\.Base64\s*\)', expression):
            matches = [''.join(re.findall(r'"([A-Za-z0-9+/=]+)"', chunks[1]))]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError('Expected a single embedded payload per partition')
    blob = base64.b64decode(matches[0], validate=False)
    if 'Binary.Decompress' in expression:
        if 'Compression.GZip' in expression:
            blob = zlib.decompress(blob, 16 + zlib.MAX_WBITS)
        else:
            try:
                blob = zlib.decompress(blob, -zlib.MAX_WBITS)
            except zlib.error:
                blob = zlib.decompress(blob)
    text = blob.decode('utf-8-sig')
    if 'Csv.Document' in expression:
        return {'bytes': blob, 'rows': list(csv.DictReader(io.StringIO(text))), 'format': 'CSV'}
    parsed = json.loads(text)
    return {'bytes': blob, 'rows': parsed, 'format': 'JSON'}


def validate_model(v, model_path, clean_path, metrics):
    model_doc = v.load(model_path)
    model = model_doc.get('model', {})
    tables = model.get('tables', [])
    names = [t.get('name') for t in tables]
    v.record('model_unique_table_names', all(names) and len(set(names)) == len(names), names)
    v.record('model_compatibility_level', model_doc.get('compatibilityLevel', 0) >= 1500, model_doc.get('compatibilityLevel'))
    columns = {t['name']: {c['name'] for c in t.get('columns', [])} for t in tables}
    measures = {t['name']: {m['name'] for m in t.get('measures', [])} for t in tables}
    all_measures = [m['name'] for t in tables for m in t.get('measures', [])]
    v.record('model_unique_measure_names', len(set(all_measures)) == len(all_measures), {'count': len(all_measures)})
    v.record('model_has_measures', bool(all_measures), {'count': len(all_measures)})
    for t in tables:
        fields = [c['name'] for c in t.get('columns', [])]
        v.record('model_unique_columns:' + t['name'], len(set(fields)) == len(fields), {'count': len(fields)})
        v.record('model_partition:' + t['name'], bool(t.get('partitions')), {'count': len(t.get('partitions', []))})
        sort_fields = [c.get('sortByColumn') for c in t.get('columns', []) if c.get('sortByColumn')]
        v.record('sort_columns:' + t['name'], all(c in fields for c in sort_fields), sort_fields)
    for relation in model.get('relationships', []):
        valid = all(relation.get(side + 'Table') in columns and relation.get(side + 'Column') in columns[relation[side + 'Table']] for side in ['from', 'to'])
        v.record('relationship:' + relation.get('name', '<unnamed>'), valid, relation)
    # Validate explicit table-qualified DAX field references. Do not claim a DAX parser.
    qualified = re.compile(r"(?:'([^']+)'|\b([A-Za-z_][A-Za-z0-9_]*))\[([^\]]+)\]")
    dax_refs = []
    dax_bad = []
    bare_bad = []
    measure_graph = {}
    known_measures = {name.lower(): name for name in all_measures}
    for t in tables:
        for item in t.get('measures', []) + [c for c in t.get('columns', []) if 'expression' in c]:
            expression = expr_text(item.get('expression'))
            scrubbed = re.sub(r'"(?:[^"]|"")*"', '""', expression)
            qualified_measure_dependencies = []
            for match in qualified.finditer(scrubbed):
                table = match[1] or match[2]
                field = match[3]
                dax_refs.append((table, field))
                if table not in columns or field not in columns.get(table, set()) | measures.get(table, set()):
                    dax_bad.append({'owner': t['name'] + '.' + item['name'], 'table': table, 'field': field})
                elif field in measures.get(table, set()):
                    qualified_measure_dependencies.append(field)
            residual = qualified.sub('', scrubbed)
            bare_refs = re.findall(r'\[([^\]]+)\]', residual)
            for ref in bare_refs:
                if ref.lower() not in known_measures:
                    bare_bad.append({'owner': t['name'] + '.' + item['name'], 'unqualified_measure': ref})
            if item['name'] in all_measures:
                measure_graph[item['name']] = qualified_measure_dependencies + [known_measures[ref.lower()] for ref in bare_refs if ref.lower() in known_measures]
    v.record('qualified_dax_field_references', not dax_bad, {'references_checked': len(dax_refs), 'invalid': dax_bad, 'scope': 'Reference spelling only. DAX was not executed.'})
    v.record('unqualified_dax_measure_references', not bare_bad, {'invalid': bare_bad, 'scope': 'Known named measures only; no DAX expression evaluation.'})
    cycles = []
    visited = set()
    def visit_measure(name, stack):
        if name in stack:
            cycles.append(stack[stack.index(name):] + [name])
        elif name not in visited:
            for dependency in measure_graph.get(name, []):
                visit_measure(dependency, stack + [name])
            visited.add(name)
    for name in measure_graph:
        visit_measure(name, [])
    v.record('measure_dependency_cycles', not cycles, cycles or 'No cycles in statically extracted named-measure references.')
    clean_raw = clean_path.read_bytes()
    clean_rows = list(csv.DictReader(io.StringIO(clean_raw.decode('utf-8-sig'))))
    embedded = []
    decoded_tables = {}
    for t in tables:
        for partition in t.get('partitions', []):
            source = partition.get('source', {})
            v.record('import_mode:' + t['name'], partition.get('mode') == 'import', partition.get('mode'))
            expression = expr_text(source.get('expression'))
            external = bool(re.search(r'(?:File\.Contents|Folder\.Files|Web\.Contents|Sql\.Database)\s*\(', expression))
            v.record('portable_partition:' + t['name'], not external, {'source_type': source.get('type'), 'external_data_source': external})
            try:
                decoded = decode_embedded_source(expression)
            except Exception as exc:
                v.record('embedded_decode:' + t['name'], False, str(exc))
                continue
            if decoded is None:
                continue
            rows = decoded['rows']
            entry = {'table': t['name'], 'format': decoded['format'], 'payload_sha256': sha256(decoded['bytes']), 'rows': len(rows)}
            embedded.append(entry)
            if rows and isinstance(rows[0], dict):
                decoded_tables[t['name']] = rows
                source_fields = set(rows[0])
                model_fields = {c.get('sourceColumn') for c in t.get('columns', []) if 'sourceColumn' in c}
                v.record('source_columns:' + t['name'], source_fields == model_fields, {'source_column_count': len(source_fields), 'model_column_count': len(model_fields), 'missing_from_model': sorted(source_fields - model_fields), 'missing_from_source': sorted(model_fields - source_fields)})
                type_errors = []
                for column in t.get('columns', []):
                    field, dtype = column.get('sourceColumn'), column.get('dataType')
                    if not field:
                        continue
                    for index, row in enumerate(rows, 1):
                        value = row.get(field)
                        if value in ('', None):
                            continue
                        try:
                            if dtype == 'int64':
                                number = int(value)
                                if not -(2**63) <= number < 2**63:
                                    raise ValueError('integer outside int64 range')
                            elif dtype == 'double' and not math.isfinite(float(value)):
                                raise ValueError('nonfinite number')
                            elif dtype == 'dateTime':
                                datetime.fromisoformat(value)
                        except (ValueError, TypeError):
                            if len(type_errors) < 10:
                                type_errors.append({'row': index, 'column': field, 'type': dtype, 'value': value})
                v.record('source_types:' + t['name'], not type_errors, type_errors or 'All nonblank source values fit their declared model scalar types.')
            if rows and isinstance(rows[0], dict) and 'booking_id' in rows[0]:
                exact = rows == clean_rows
                value = sum(float(r['booking_value_inr']) for r in rows)
                totals = metrics['totals']
                expected = {'rows': totals['bookings'], 'value': totals['booking_value_inr'], 'users': totals['total_users'], 'train_numbers': totals['distinct_train_numbers'], 'passengers': totals['passengers'], 'invalid_chronology': totals['invalid_chronology_count']}
                actual = {'rows': len(rows), 'value': value, 'users': len({r['user_id'] for r in rows}), 'train_numbers': len({r['train_number'] for r in rows}), 'passengers': sum(int(r['passenger_count']) for r in rows), 'invalid_chronology': sum(str(r['flag_invalid_chronology']).lower() in ('true', '1') for r in rows)}
                v.record('embedded_bookings_match_clean_csv', exact, {'embedded_records': len(rows), 'source_records': len(clean_rows), 'full_row_and_column_equality': exact, 'exact_csv_byte_equality': decoded['bytes'] == clean_raw})
                v.record('embedded_booking_controls', expected == actual, {'expected': expected, 'actual': actual})
                v.summary['embedded_bookings_verified'] = exact and expected == actual
    for relation in model.get('relationships', []):
        from_rows, to_rows = decoded_tables.get(relation.get('fromTable')), decoded_tables.get(relation.get('toTable'))
        if from_rows is None or to_rows is None:
            continue
        from_values = {r[relation['fromColumn']] for r in from_rows}
        to_values = [r[relation['toColumn']] for r in to_rows]
        missing = sorted(from_values - set(to_values))
        unique = len(set(to_values)) == len(to_values)
        v.record('relationship_data:' + relation['name'], not missing and (unique or relation.get('toCardinality') != 'one'), {'missing_foreign_keys': missing, 'to_side_unique': unique, 'from_unique_values': len(from_values), 'to_records': len(to_values)})
    v.record('embedded_booking_source_present', v.summary.get('embedded_bookings_verified') is True, embedded)
    v.summary.update({'tables': len(tables), 'measures': len(all_measures), 'relationships': len(model.get('relationships', [])), 'embedded_sources': embedded})
    return columns, measures


def validate_report(v, report_dir, report_documents, columns, measures):
    definition = report_dir / 'definition'
    for required in ['version.json', 'report.json', 'pages/pages.json']:
        v.record('required_report_file:' + required, (definition / required).is_file(), required)
    report_metadata = json.loads((definition / 'report.json').read_text())
    resources = {}
    for package in report_metadata.get('resourcePackages', []):
        package_name = package.get('name')
        for item in package.get('items', []):
            resource = v.resolve(report_dir / 'StaticResources' / package_name, item.get('path'), 'report_resource:' + str(item.get('name')))
            resources[(package_name, item.get('name'))] = resource
            if resource.is_file() and resource.suffix.lower() == '.json':
                v.load(resource)
    for role, theme in report_metadata.get('themeCollection', {}).items():
        if isinstance(theme, dict):
            key = (theme.get('type'), theme.get('name'))
            v.record('theme_resource_binding:' + role, key in resources, {'resource_package': key[0], 'name': key[1]})
    pages_root = definition / 'pages'
    page_files = sorted(pages_root.glob('*/page.json'))
    pages = [(path, json.loads(path.read_text())) for path in page_files]
    names = [p['name'] for _, p in pages]
    v.record('report_pages_present', bool(pages), names)
    v.record('page_ids_unique', len(set(names)) == len(names), names)
    pages_meta = json.loads((pages_root / 'pages.json').read_text())
    order = pages_meta.get('pageOrder', [])
    v.record('page_order_complete', len(order) == len(set(order)) and set(order) == set(names), {'pageOrder': order, 'pageIds': names})
    v.record('active_page_exists', pages_meta.get('activePageName') in names, pages_meta.get('activePageName'))
    visuals = []
    for page_path, page in pages:
        v.record('page_folder_id:' + page['name'], page_path.parent.name == page['name'], page_path.parent.name)
        width, height = page.get('width', 0), page.get('height', 0)
        data_rectangles = []
        for visual_path in sorted((page_path.parent / 'visuals').glob('*/visual.json')):
            visual = json.loads(visual_path.read_text())
            ident = visual.get('name')
            position = visual.get('position', {})
            x, y, w, h = [position.get(k, -1) for k in ['x', 'y', 'width', 'height']]
            inside = min(x, y) >= 0 and min(w, h) > 0 and x + w <= width + 0.01 and y + h <= height + 0.01
            v.record('visual_bounds:' + str(ident), inside, {'page': page['name'], 'position': position, 'canvas': [width, height]})
            v.record('visual_folder_id:' + str(ident), visual_path.parent.name == ident, visual_path.parent.name)
            type_name = visual.get('visual', {}).get('visualType')
            query_refs = {node['queryRef'] for _, node in walk(visual.get('visual', {}).get('query', {})) if isinstance(node, dict) and isinstance(node.get('queryRef'), str)}
            metadata_selectors = [node['selector']['metadata'] for _, node in walk(visual) if isinstance(node, dict) and isinstance(node.get('selector'), dict) and 'metadata' in node['selector']]
            if metadata_selectors:
                invalid_selectors = [metadata for metadata in metadata_selectors if metadata not in query_refs]
                v.record('formatting_metadata_bindings:' + page['name'] + '/' + str(ident), not invalid_selectors, {'selectors': len(metadata_selectors), 'unresolved': invalid_selectors})
            if type_name in {'cardVisual', 'lineChart', 'barChart', 'columnChart', 'clusteredBarChart', 'clusteredColumnChart', 'tableEx', 'slicer', 'pieChart', 'donutChart'}:
                state = visual.get('visual', {}).get('query', {}).get('queryState', {})
                projection_count = sum(len(role.get('projections', [])) for role in state.values() if isinstance(role, dict))
                v.record('data_visual_projection:' + str(ident), projection_count > 0, {'type': type_name, 'projection_count': projection_count})
                data_rectangles.append((ident, x, y, w, h))
                required_roles = {'cardVisual': {'Data'}, 'lineChart': {'Category', 'Y'}, 'barChart': {'Category', 'Y'}, 'slicer': {'Values'}, 'tableEx': {'Values'}}.get(type_name)
                if required_roles:
                    populated_roles = {name for name, role in state.items() if isinstance(role, dict) and role.get('projections')}
                    v.record('native_visual_roles:' + str(ident), required_roles <= populated_roles, {'type': type_name, 'required_for_this_report': sorted(required_roles), 'populated_roles': sorted(populated_roles)})
            visuals.append({'name': ident, 'page': page['name'], 'type': type_name})
        overlaps = []
        for i, first in enumerate(data_rectangles):
            for second in data_rectangles[i+1:]:
                overlap_w = min(first[1] + first[3], second[1] + second[3]) - max(first[1], second[1])
                overlap_h = min(first[2] + first[4], second[2] + second[4]) - max(first[2], second[2])
                if overlap_w > 0.5 and overlap_h > 0.5:
                    overlaps.append({'visuals': [first[0], second[0]], 'overlap_area': round(overlap_w * overlap_h, 2)})
        v.record('data_visual_overlap:' + page['name'], not overlaps, overlaps or 'No overlapping data-visual rectangles. Background shapes/text are excluded.')
        page_ids = {visual['name'] for visual in visuals if visual['page'] == page['name']}
        interaction_errors = []
        interaction_pairs = []
        for interaction in page.get('visualInteractions', []):
            source, destination = interaction.get('source'), interaction.get('target')
            interaction_pairs.append((source, destination))
            if source not in page_ids or destination not in page_ids or source == destination:
                interaction_errors.append(interaction)
        v.record('visual_interaction_endpoints:' + page['name'], not interaction_errors, {'interactions': len(interaction_pairs), 'invalid': interaction_errors})
        v.record('visual_interaction_pairs_unique:' + page['name'], len(set(interaction_pairs)) == len(interaction_pairs), {'interactions': len(interaction_pairs)})
    ids = [(x['page'], x['name']) for x in visuals]
    v.record('visual_ids_unique_within_page', bool(ids) and len(set(ids)) == len(ids), {'count': len(ids), 'scope': 'Visual names are scoped to their containing page, per the official visualContainer schema.'})
    field_references(v, report_documents, columns, measures)
    v.summary.update({'pages': len(pages), 'visuals': len(visuals), 'visual_types': dict(Counter(x['type'] for x in visuals))})


def run(args):
    project = args.project.resolve()
    v = Validation(project)
    try:
        from jsonschema import validators
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT7
    except ImportError:
        v.record('schema_validator_dependency', False, 'Install optional dependency: python -m pip install jsonschema')
        return v
    schema_store = OfficialSchemas(args.schema_cache)
    registry = Registry(retrieve=lambda uri: Resource.from_contents(schema_store.get(uri), default_specification=DRAFT7))
    powerbi = project / 'powerbi'
    try:
        pbip_path = powerbi / 'IRCTC.pbip'
        pbip = v.load(pbip_path)
        artifacts = pbip.get('artifacts', [])
        report_refs = [a['report']['path'] for a in artifacts if isinstance(a, dict) and 'report' in a]
        v.record('pbip_single_report', len(report_refs) == 1, report_refs)
        if len(report_refs) != 1:
            return v
        report_dir = v.resolve(powerbi, report_refs[0], 'pbip_report_path')
        pbir_path = report_dir / 'definition.pbir'
        pbir = v.load(pbir_path)
        model_ref = pbir.get('datasetReference', {}).get('byPath', {}).get('path')
        model_dir = v.resolve(report_dir, model_ref, 'report_model_path')
        pbism_path = model_dir / 'definition.pbism'
        pbism = v.load(pbism_path)
        schema_documents = [(pbip_path, pbip), (pbir_path, pbir), (pbism_path, pbism)]
        report_documents = []
        for path in sorted((report_dir / 'definition').rglob('*.json')):
            document = v.load(path)
            report_documents.append((path, document))
            schema_documents.append((path, document))
        for path in [report_dir / '.platform', model_dir / '.platform']:
            if path.exists():
                schema_documents.append((path, v.load(path)))
        for path, document in schema_documents:
            if not document.get('$schema'):
                v.record('schema_declaration:' + v.relative(path), False, 'Expected an official $schema declaration')
            else:
                validate_schema(v, schema_store, path, document, registry, validators)
        metrics = json.loads((project / 'reports' / 'metrics.json').read_text())
        columns, measures = validate_model(v, model_dir / 'model.bim', project / 'data/processed/bookings_clean.csv', metrics)
        validate_report(v, report_dir, report_documents, columns, measures)
        v.summary['official_schema_files'] = len(v.schemas)
        v.summary['official_schema_resources'] = len(schema_store.loaded)
        # Negative control proves that the selected official schema actually rejects malformed instances.
        visual_docs = [(p, d) for p, d in report_documents if p.name == 'visual.json']
        if visual_docs:
            path, good_doc = visual_docs[0]
            schema = schema_store.get(good_doc['$schema'])
            bad_doc = dict(good_doc)
            bad_doc['position'] = {'x': 'invalid-coordinate'}
            validator_cls = validators.validator_for(schema)
            validator = validator_cls(schema, registry=registry, format_checker=validator_cls.FORMAT_CHECKER)
            v.record('schema_negative_control', bool(list(validator.iter_errors(bad_doc))), 'A malformed visual coordinate must be rejected by the official visual schema.')
    except Exception as exc:
        v.record('validation_execution', False, f'{type(exc).__name__}: {exc}')
    return v


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--schema-cache', type=Path, default=Path(tempfile.gettempdir()) / 'irctc-powerbi-schemas')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    v = run(args)
    result = {'status': 'passed' if not v.errors else 'failed', 'validated_at_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'Official Microsoft JSON schemas, project references, model field references, visual bounds and embedded-source equality. No Power BI engine was run.', 'not_tested': ['Power BI Desktop file opening', 'Power Query M execution and refresh', 'DAX evaluation and filter behavior', 'Desktop visual rendering', 'PBIX serialization'], 'summary': v.summary, 'checks': v.checks, 'errors': v.errors, 'warnings': v.warnings, 'schemas': v.schemas, 'files': v.files}
    output = args.output or args.project / 'reports/powerbi_validation.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'checks': len(v.checks), 'errors': v.errors, 'summary': v.summary}, indent=2))
    return 1 if v.errors else 0


if __name__ == '__main__':
    raise SystemExit(main())

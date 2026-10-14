#!/usr/bin/env python3
"""Build the three native PBIR report pages. Standard library only.

Close Desktop before rebuilding: generated pages are overwritten. The packaged
Microsoft base theme is retained. Windows Desktop refresh/render/save remains
the native acceptance step; JSON generation is not PBIX serialization.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / 'powerbi'
REPORT = PBI / 'IRCTC.Report'
SCHEMA = 'https://developer.microsoft.com/json-schemas/'
BLUE, RED, INK, MUTED = '#0E48B6', '#F42829', '#172443', '#586780'
PALE, LINE = '#F5F8FD', '#DCE4F0'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def expr(value):
    if isinstance(value, bool):
        literal = str(value).lower()
    elif isinstance(value, (int, float)):
        literal = str(value) + 'D'
    else:
        literal = "'" + value.replace("'", "''") + "'"
    return {'expr': {'Literal': {'Value': literal}}}


def fill(color):
    return {'solid': {'color': expr(color)}}


def obj(props, selector=None):
    item = {'properties': props}
    if selector is not None:
        item['selector'] = selector
    return [item]


def field(name, kind='Measure', table='Bookings'):
    return {kind: {'Expression': {'SourceRef': {'Entity': table}}, 'Property': name}}


def projection(name, kind='Measure', table='Bookings', active=False, label=None):
    result = {'field': field(name, kind, table), 'queryRef': table + '.' + name,
              'nativeQueryRef': label or name}
    if active:
        result['active'] = True
    return result


def role(*projections):
    return {'projections': list(projections)}


def sort(name, kind='Measure', table='Bookings', direction='Descending'):
    return {'sort': [{'field': field(name, kind, table), 'direction': direction}],
            'isDefaultSort': False}


def container(title=None, pad=12, transparent=False):
    return {
        'background': obj({'show': expr(not transparent), 'color': fill('#FFFFFF'), 'transparency': expr(0)}),
        'border': obj({'show': expr(not transparent), 'color': fill(LINE), 'radius': expr(8)}),
        'padding': obj({k: expr(pad) for k in ('top', 'bottom', 'left', 'right')}),
        'title': obj({'show': expr(bool(title)), 'text': expr(title or ''),
                      'fontColor': fill(INK), 'fontSize': expr(13), 'bold': expr(True)}),
    }


class Page:
    def __init__(self, name, title):
        self.name, self.title, self.visuals = name, title, []

    def add(self, ident, kind, rect, query=None, objects=None, vco=None):
        x, y, width, height = rect
        order = (len(self.visuals) + 1) * 1000
        visual = {'visualType': kind}
        if query:
            visual['query'] = query
        if objects:
            visual['objects'] = objects
        visual['visualContainerObjects'] = vco or container()
        result = {'$schema': SCHEMA + 'fabric/item/report/definition/visualContainer/2.9.0/schema.json',
                  'name': ident, 'position': dict(x=x, y=y, z=order, width=width, height=height, tabOrder=order),
                  'visual': visual}
        self.visuals.append(result)

    def text(self, ident, text, rect, size=16, color=INK, bold=False):
        paragraphs = [{'textRuns': [{'value': line, 'textStyle': {
            'fontFamily': 'Segoe UI Semibold' if bold else 'Segoe UI',
            'fontSize': str(size) + 'px', 'color': color}}], 'horizontalTextAlignment': 'left'}
            for line in text.split('\n')]
        self.add(ident, 'textbox', rect, objects={'general': obj({'paragraphs': paragraphs})},
                 vco=container(pad=0, transparent=True))

    def header(self, subtitle, number):
        self.text('page_title', self.title, (40, 24, 1120, 48), 30, BLUE, True)
        self.text('page_subtitle', subtitle, (40, 76, 1520, 28), 16, MUTED)
        self.text('page_number', f'IRCTC  /  {number:02d}', (1330, 32, 230, 34), 19, BLUE, True)
        filters = [('month', 'year_month', 'DimDate', 'Booking month'),
                   ('channel', 'booking_channel', 'Bookings', 'Booking channel'),
                   ('type', 'booking_type', 'Bookings', 'Booking type'),
                   ('status', 'booking_status', 'Bookings', 'Booking status'),
                   ('route', 'route', 'Bookings', 'Route')]
        for i, (ident, col, table, label) in enumerate(filters):
            self.add('filter_' + ident, 'slicer', (40 + i * 308, 114, 288, 80),
                     query={'queryState': {'Values': role(projection(col, 'Column', table))},
                            'sortDefinition': sort(col, 'Column', table, 'Ascending')},
                     objects={'data': obj({'mode': expr('Dropdown')}),
                              'header': obj({'show': expr(True), 'text': expr(label),
                                             'fontColor': fill(INK), 'textSize': expr(11)})},
                     vco=container(pad=8))

    def card(self, ident, measure, label, rect, color=BLUE, size=26):
        default = {'id': 'default'}
        self.add(ident, 'cardVisual', rect,
                 query={'queryState': {'Data': role(projection(measure))}},
                 objects={
                     'value': obj({'fontSize': expr(size), 'fontColor': fill(color), 'bold': expr(True)}, default),
                     'label': obj({'show': expr(True), 'text': expr(label), 'fontSize': expr(12), 'fontColor': fill(MUTED)}, default),
                     'outline': obj({'show': expr(False)}, default),
                     'accentBar': obj({'show': expr(True), 'position': expr('Left'), 'width': expr(4), 'color': fill(color)}, default),
                     'layout': obj({k: expr(0) for k in ('topOuterMargin', 'bottomOuterMargin', 'leftOuterMargin', 'rightOuterMargin', 'paddingUniform')}, default),
                     'padding': obj({'topMargin': expr(8), 'bottomMargin': expr(8), 'leftMargin': expr(16), 'rightMargin': expr(8)}, default),
                     'spacing': obj({'customizeSpacing': expr(True), 'verticalSpacing': expr(4)}, default),
                 }, vco=container(pad=0))

    def chart(self, ident, kind, title, category, measure, rect, table='Bookings', series=None,
              color=BLUE, chronological=False):
        state = {'Category': role(projection(category, 'Column', table, active=True)),
                 'Y': role(projection(measure))}
        if series:
            state['Series'] = role(projection(series, 'Column'))
        objects = {'categoryAxis': obj({'showAxisTitle': expr(False), 'fontSize': expr(10), 'labelColor': fill(MUTED)}),
                   'valueAxis': obj({'showAxisTitle': expr(False), 'fontSize': expr(10), 'labelColor': fill(MUTED),
                                     'gridlineColor': fill(LINE)}),
                   'legend': obj({'show': expr(bool(series)), 'showTitle': expr(False), 'fontSize': expr(10), 'position': expr('Top')}),
                   'labels': obj({'show': expr(False)})}
        if not series:
            objects['dataPoint'] = obj({'fill': fill(color)}, {'metadata': 'Bookings.' + measure})
        if kind == 'lineChart':
            objects['lineStyles'] = obj({'strokeWidth': expr(3), 'showMarker': expr(True), 'markerSize': expr(5)})
        self.add(ident, kind, rect, query={'queryState': state,
                 'sortDefinition': sort(category, 'Column', table, 'Ascending') if chronological else sort(measure)},
                 objects=objects, vco=container(title))

    def table(self, ident, title, columns, measures, rect, sort_measure='Bookings'):
        projs = [projection(col, 'Column', label=label) for col, label in columns]
        projs += [projection(name, label=label) for name, label in measures]
        vco = container(title)
        vco['stylePreset'] = obj({'name': expr('None')})
        self.add(ident, 'tableEx', rect, query={'queryState': {'Values': role(*projs)},
                 'sortDefinition': sort(sort_measure)}, objects={
                     'columnHeaders': obj({'autoSizeColumnWidth': expr(True), 'columnAdjustment': expr('growToFit'),
                                           'fontColor': fill(BLUE), 'backColor': fill('#EAF0FC'), 'fontSize': expr(10), 'wordWrap': expr(True)}),
                     'values': obj({'fontSize': expr(10), 'backColorPrimary': fill('#FFFFFF'), 'backColorSecondary': fill(PALE),
                                    'fontColorPrimary': fill(INK), 'fontColorSecondary': fill(INK)}),
                     'grid': obj({'rowPadding': expr(5), 'gridVertical': expr(False), 'gridHorizontal': expr(False)})}, vco=vco)

    def save(self):
        path = REPORT / 'definition/pages' / self.name
        names = {v['name'] for v in self.visuals}
        assert len(names) == len(self.visuals)
        # Make selections filter other data visuals, rather than mixing highlights
        # with recalculated cards. Slicers remain independently clearable.
        selectable = [v for v in self.visuals if v['visual']['visualType'] in ('slicer', 'lineChart', 'barChart', 'tableEx')]
        targets = [v for v in self.visuals if v['visual']['visualType'] not in ('textbox', 'slicer')]
        interactions = [{'source': source['name'], 'target': target['name'], 'type': 'DataFilter'}
                        for source in selectable for target in targets if source['name'] != target['name']]
        write(path / 'page.json', {
            '$schema': SCHEMA + 'fabric/item/report/definition/page/2.1.0/schema.json',
            'name': self.name, 'displayName': self.title, 'displayOption': 'FitToPage', 'width': 1600, 'height': 1000,
            'objects': {'background': obj({'color': fill(PALE), 'transparency': expr(0)})},
            'visualInteractions': interactions})
        for visual in self.visuals:
            write(path / 'visuals' / visual['name'] / 'visual.json', visual)
        return {'id': self.name, 'title': self.title, 'visuals': len(self.visuals)}


def overview():
    p = Page('overview', 'Booking overview')
    p.header('Demand, recorded value and channel mix  |  Synthetic educational sample  |  Booking dates: 2025', 1)
    cards = [('Bookings', 'Accepted bookings', BLUE), ('Recorded Booking Value', 'Recorded booking value · INR', RED),
             ('Distinct Users', 'Distinct users', BLUE), ('Distinct Train Numbers', 'Distinct train numbers', BLUE),
             ('Mean Reported Occupancy Pct', 'Mean record occupancy', BLUE)]
    for i, (measure, label, color) in enumerate(cards):
        p.card('kpi_' + str(i), measure, label, (40 + 308*i, 214, 288, 116), color, 24 if i == 1 else 26)
    p.chart('monthly_bookings', 'lineChart', 'Booking trend · booking month', 'year_month', 'Bookings',
            (40, 350, 744, 270), table='DimDate', chronological=True)
    p.chart('channel_type_value', 'barChart', 'Recorded value · booking type & channel', 'booking_type', 'Recorded Booking Value',
            (804, 350, 756, 270), series='booking_channel')
    p.chart('route_bookings', 'barChart', 'Routes ranked by bookings', 'route', 'Bookings', (40, 640, 744, 284))
    p.chart('status_value', 'barChart', 'Recorded value by booking status', 'booking_status', 'Recorded Booking Value',
            (804, 640, 756, 284), color=RED)
    p.text('metric_note', 'All selected statuses are included. Recorded value is a source amount; occupancy is a booking-record mean.\nTrain numbers do not establish trains operated. Use page tabs below; each page has its own filters.',
           (40, 944, 1520, 48), 14, MUTED)
    return p.save()


def routes():
    p = Page('routes_customers', 'Routes & customers')
    p.header('Compare route value, passenger records and booking mix  |  Select a route or chart bar to explore', 2)
    cards = [('Passengers', 'Passengers on booking records', BLUE), ('Average Booking Value', 'Average booking value · INR', RED),
             ('Cancellation Rate', 'Cancellation rate', RED), ('Users With Multiple Selected Bookings', 'Users with repeat selected bookings', BLUE)]
    for i, (measure, label, color) in enumerate(cards):
        p.card('kpi_' + str(i), measure, label, (40+385*i, 214, 365, 116), color)
    p.table('route_detail', 'Route comparison · share within selected routes', [('route', 'Route')],
            [('Bookings', 'Bookings'), ('Recorded Booking Value', 'Recorded value'), ('Selected Route Value Share', 'Value share'),
             ('Passengers', 'Passengers'), ('Average Booking Value', 'Average value'), ('Cancellation Rate', 'Cancellation rate')],
            (40, 350, 1520, 280))
    p.chart('class_value', 'barChart', 'Recorded value by travel class', 'travel_class', 'Recorded Booking Value',
            (40, 650, 494, 274), color=RED)
    p.chart('train_type_bookings', 'barChart', 'Bookings by train type', 'train_type', 'Bookings', (554, 650, 493, 274))
    p.chart('payment_value', 'barChart', 'Recorded value by payment method', 'payment_method', 'Recorded Booking Value',
            (1067, 650, 493, 274), color=RED)
    p.text('route_note', 'Passengers are people on booking records, not confirmed journeys. Repeat users are counted within the current selection.\nRoute and train-type comparisons describe this synthetic sample; they do not establish profitability or operational demand.',
           (40, 944, 1520, 48), 14, MUTED)
    return p.save()


def quality():
    p = Page('data_quality', 'Data quality')
    p.header('Trace the source reconciliation, then inspect the selected records  |  Resolve limitations before making decisions', 3)
    p.text('fixed_heading', 'FULL SOURCE SNAPSHOT  ·  These five controls do not change with filters', (40, 208, 1520, 28), 15, BLUE, True)
    fixed = [('Raw Source Records', 'Raw source records', BLUE), ('Exact Duplicates Removed', 'Exact duplicate removed', RED),
             ('Quarantined Records', 'Conflicting rows quarantined', RED), ('Conflicting Booking IDs', 'Conflicting booking IDs', RED),
             ('Accepted Source Records', 'Accepted source records', BLUE)]
    for i, (measure, label, color) in enumerate(fixed):
        p.card('source_' + str(i), measure, label, (40 + 308*i, 244, 288, 102), color, 24)
    p.text('amount_reconciliation', 'Full-source amount reconciliation · ₹53,055,565 − ₹660 − ₹1,775,602 = ₹51,279,303',
           (40, 360, 1520, 30), 19, INK, True)
    p.text('selected_heading', 'CURRENT SELECTION  ·  Descriptive totals retain flagged dates; lead-time metrics exclude them',
           (40, 400, 1520, 28), 15, BLUE, True)
    cards = [('Invalid Chronology Records', 'Booked after travel', RED), ('Invalid Chronology Rate', 'Invalid chronology rate', RED),
             ('Valid Lead Time Records', 'Valid lead-time records', BLUE), ('Mean Valid Lead Time Days', 'Mean valid lead time · days', BLUE),
             ('Charge Mismatch Records', 'Charge component mismatches', BLUE)]
    for i, (measure, label, color) in enumerate(cards):
        p.card('selected_' + str(i), measure, label, (40 + 308*i, 438, 288, 110), color, 24)
    p.chart('chronology_month', 'lineChart', 'Invalid chronology rate · booking month', 'year_month', 'Invalid Chronology Rate',
            (40, 568, 744, 266), table='DimDate', color=RED, chronological=True)
    p.table('route_quality', 'Source flags by route · record counts', [('route', 'Route')],
            [('Bookings', 'Bookings'), ('Invalid Chronology Records', 'Date flags'),
             ('Occupancy Conflict Records', 'Occupancy conflicts'), ('Delay Conflict Records', 'Delay conflicts')],
            (804, 568, 756, 266))
    p.text('quality_notes', 'WHAT THE SOURCE CANNOT ESTABLISH', (40, 854, 1520, 28), 16, BLUE, True)
    p.text('quality_details', 'All 540 train numbers have inconsistent names, routes or zones. Occupancy and delay can conflict within a train and travel date.\nThese fields support record-level descriptions only. Missing service, refund and payment-settlement data prevent reliable load-factor or net-revenue claims.\nEvery conflicting-ID row is quarantined; no arbitrary survivor is used. The original CSV and exception exports remain in the portfolio package.',
           (40, 890, 1520, 88), 15, MUTED)
    return p.save()


def main():
    base = REPORT / 'StaticResources/SharedResources/BaseThemes/CY24SU02.json'
    if not base.is_file():
        raise SystemExit('Missing packaged Microsoft base theme: ' + str(base))
    write(PBI / 'IRCTC.pbip', {
        '$schema': SCHEMA + 'fabric/pbip/pbipProperties/1.0.0/schema.json', 'version': '1.0',
        'artifacts': [{'report': {'path': 'IRCTC.Report'}}], 'settings': {'enableAutoRecovery': True}})
    write(REPORT / 'definition.pbir', {
        '$schema': SCHEMA + 'fabric/item/report/definitionProperties/2.0.0/schema.json', 'version': '4.0',
        'datasetReference': {'byPath': {'path': '../IRCTC.SemanticModel'}}})
    write(REPORT / 'definition/version.json', {
        '$schema': SCHEMA + 'fabric/item/report/definition/versionMetadata/1.0.0/schema.json', 'version': '2.0.0'})
    theme = json.loads((PBI / 'IRCTC_Theme.json').read_text())
    theme['name'] = 'IRCTC_Theme.json'
    write(REPORT / 'StaticResources/RegisteredResources/IRCTC_Theme.json', theme)
    write(REPORT / 'definition/report.json', {
        '$schema': SCHEMA + 'fabric/item/report/definition/report/3.3.0/schema.json',
        'themeCollection': {
            'baseTheme': {'name': 'CY24SU02', 'reportVersionAtImport': {'visual': '1.8.89', 'report': '2.0.89', 'page': '1.3.89'}, 'type': 'SharedResources'},
            'customTheme': {'name': 'IRCTC_Theme.json', 'reportVersionAtImport': {'visual': '2.9.0', 'report': '3.3.0', 'page': '2.1.0'}, 'type': 'RegisteredResources'}},
        'resourcePackages': [
            {'name': 'SharedResources', 'type': 'SharedResources', 'items': [{'name': 'CY24SU02', 'path': 'BaseThemes/CY24SU02.json', 'type': 'BaseTheme'}]},
            {'name': 'RegisteredResources', 'type': 'RegisteredResources', 'items': [{'name': 'IRCTC_Theme.json', 'path': 'IRCTC_Theme.json', 'type': 'CustomTheme'}]}],
        'settings': {'useStylableVisualContainerHeader': True, 'useEnhancedTooltips': True, 'allowChangeFilterTypes': True}})
    pages = [overview(), routes(), quality()]
    write(REPORT / 'definition/pages/pages.json', {
        '$schema': SCHEMA + 'fabric/item/report/definition/pagesMetadata/1.0.0/schema.json',
        'pageOrder': [p['id'] for p in pages], 'activePageName': 'overview'})
    print(json.dumps({'status': 'generated', 'pages': pages, 'native_desktop_verified': False}, indent=2))


if __name__ == '__main__':
    main()

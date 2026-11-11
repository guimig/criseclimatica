"""Empirical unit hypotheses, explicitly distinct from documented units."""
from collections import defaultdict
from .analysis import valid_number

VERSION = 'sensor-unit-inference-v1'


def annotate(feed):
    groups = defaultdict(list)
    for s in feed.get('stations', []):
        for r in s.get('readings', []):
            if not r.get('unit') and valid_number(r.get('value')):
                groups[r['sensor_id']].append(r['value'])
    report = []
    for sensor, values in sorted(groups.items()):
        unit, status, alternatives = None, 'ambiguous', []
        rationale = 'Magnitude alone cannot distinguish the unit or reference datum.'
        if sensor == 240:
            unit, status, alternatives = 'mm/h', 'probable', ['mm/min', 'mm/s', 'scaled_rate']
            rationale = ('Catalog identifies precipitation intensity; mm/h is dimensionally consistent with rainfall in mm. '
                         'Observed regional magnitudes are compatible; zero readings cannot discriminate scales. '
                         'No simultaneous integrated-rate versus same-instrument counter validation yet.')
        elif sensor in (330, 340, 350, 360, 610, 620) and all(0 <= v <= 100 for v in values) and any(v > 1 for v in values):
            unit, status, alternatives = '%', 'probable', ['scaled_raw_sensor_output']
            rationale = ('Catalog identifies soil moisture. Values above 1 and within 0..100 are compatible with percentage '
                         'and incompatible with an unscaled 0..1 fraction; calibration and moisture definition unverified.')
        elif sensor in (20, 260, 270):
            alternatives = ['m', 'cm', 'mm', 'sensor_reference_offset']
        entry = {'sensor_id': sensor, 'suggested_unit': unit, 'status': status, 'method_version': VERSION,
                 'sample_count': len(values), 'nonzero_count': sum(v != 0 for v in values),
                 'minimum': min(values), 'maximum': max(values), 'rationale': rationale,
                 'alternatives_not_ruled_out': alternatives, 'numeric_analysis_eligible': False}
        report.append(entry)
    by_id = {r['sensor_id']: r for r in report}
    for s in feed.get('stations', []):
        for r in s.get('readings', []):
            r['unit_status'] = 'documented' if r.get('unit') else 'inferred' if by_id.get(r['sensor_id'], {}).get('suggested_unit') else 'unresolved'
            if r['sensor_id'] in by_id and not r.get('unit'):
                r['unit_inference'] = by_id[r['sensor_id']]
    feed['unit_inference'] = report
    return feed

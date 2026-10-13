import importlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

HERE = Path(__file__).resolve().parent
NS = {'s': 'http://www.w3.org/2000/svg'}


def data():
    return json.loads((HERE / 'data.json').read_text())


def builder():
    return importlib.import_module('figures.gavel.build')


def test_snapshot_tracks_source_and_distinguishes_fixture_from_run():
    snapshot = data()
    assert len(snapshot['source']['commit']) == 40
    assert snapshot['config']['basis'] == 'illustrative source test fixtures, not a recorded run'
    assert snapshot['config']['amount_unit'] == 'cents'
    assert snapshot['source']['paths']


def test_opened_precedes_bids_and_nonaccepted_requests_do_not_append():
    snapshot = data()
    assert [event['seq'] for event in snapshot['events']] == [1, 2, 3]
    assert [event['type'] for event in snapshot['events']] == ['opened', 'bid_accepted', 'bid_accepted']
    assert [row['outcome'] for row in snapshot['requests']] == ['rejected', 'accepted', 'accepted', 'duplicate']
    bids = snapshot['events'][1:]
    assert len({bid['request_id'] for bid in bids}) == len(bids)
    duplicate = snapshot['requests'][-1]
    assert duplicate['original_seq'] == bids[0]['seq']
    assert duplicate['amount'] == bids[0]['amount']
    assert snapshot['requests'][0]['amount'] < snapshot['requests'][0]['minimum']


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_static_svg_has_complete_log_and_outcomes(mode):
    snapshot = data()
    svg = builder().render(snapshot, mode)
    root = ET.fromstring(svg)
    assert root.attrib['viewBox'] == '0 0 1280 380'
    assert root.find('s:title', NS).text == 'Every auction is one ordered log'
    assert 'fixture' in root.find('s:desc', NS).text
    cells = root.findall('.//s:g[@class="log-cell"]', NS)
    assert [int(cell.attrib['data-seq']) for cell in cells] == [event['seq'] for event in snapshot['events']]
    requests = root.findall('.//s:g[@class="bid-chip"]', NS)
    assert len(requests) == len(snapshot['requests'])
    assert len(root.findall('.//s:g[@class="rejection"]', NS)) == 1
    assert len(root.findall('.//s:g[@class="duplicate"]', NS)) == 1
    assert '@keyframes' in svg
    assert '.log-cell,.rejection,.duplicate{opacity:1}' in svg
    assert '.traveler{opacity:0}' in svg
    assert 'prefers-reduced-motion:reduce' in svg
    assert len(svg.encode()) < 400_000
    assert '<text' not in svg


def test_layout_boxes_are_inside_canvas_and_do_not_overlap():
    boxes = builder().layout(data())
    for index, (x, y, w, h) in enumerate(boxes):
        assert 40 <= x < x + w <= 1240
        assert 90 <= y < y + h <= 350
        for other_x, other_y, other_w, other_h in boxes[index + 1:]:
            assert (x + w <= other_x or other_x + other_w <= x
                    or y + h <= other_y or other_y + other_h <= y)


def test_render_uses_supplied_amounts_and_sequences():
    snapshot = data()
    snapshot['events'][1]['amount'] = 9876
    snapshot['events'][1]['seq'] = 42
    root = ET.fromstring(builder().render(snapshot, 'light'))
    cell = root.find('.//s:g[@class="log-cell"][@data-seq="42"]', NS)
    assert cell is not None
    assert '9876 cents' in cell.attrib['aria-label']
    assert '9876' in root.find('s:desc', NS).text


def test_preview_cli(tmp_path):
    from figkit.cli import main
    build = builder()
    main('gavel', HERE, build.render, data(), ['--preview', '0,7,14'], root=tmp_path)
    previews = list((tmp_path / '.preview').glob('gavel-*.svg'))
    assert len(previews) == 6
    assert all('animation-play-state:paused' in path.read_text() for path in previews)


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_text_is_readable_and_has_room_at_readme_width(monkeypatch, mode):
    runs = []
    original = builder().Outliner.run

    def capture(self, face, text, x, y, size, anchor="start"):
        width = face.advance(text, size)
        left = x - {"start": 0, "middle": width / 2, "end": width}[anchor]
        runs.append((text, size, (left, y - size, left + width, y + size / 4)))
        return original(self, face, text, x, y, size, anchor)

    monkeypatch.setattr(builder().Outliner, "run", capture)
    root = ET.fromstring(builder().render(data(), mode, freeze_at=13))
    assert runs[0][1] == 26
    assert runs[1][1] == 18
    assert all(size >= 16 for _, size, _ in runs)
    view_box = [float(v) for v in root.attrib['viewBox'].split()]
    height = view_box[3]
    for text, _, (left, top, right, bottom) in runs:
        assert 40 <= left < right <= 1240, text
        assert 0 <= top < bottom <= height - 10, text
    # Deduplicate traveler runs which duplicate the chip label at the exact same box
    unique_runs = []
    for r in runs:
        if not unique_runs or r != unique_runs[-1]:
            unique_runs.append(r)
    for index, (text, _, box) in enumerate(unique_runs):
        for other, _, next_box in unique_runs[index + 1:]:
            assert (box[2] + 2 <= next_box[0] or next_box[2] + 2 <= box[0]
                    or box[3] + 2 <= next_box[1] or next_box[3] + 2 <= box[1]), (text, other)



@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_marks_scale_with_the_larger_labels(mode):
    root = ET.fromstring(builder().render(data(), mode))
    paths = root.findall(".//s:path", NS)
    connector_paths = [p for p in paths if p.attrib.get("fill") == "none" or "M320" in p.attrib.get("d", "")]
    assert len(connector_paths) >= 2
    for path in connector_paths:
        assert float(path.attrib["stroke-width"]) == 2.5



@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_bid_chips_and_travelers_use_outcome_strokes_and_ink_text(mode):
    from figkit.color import CATEGORICAL, INK, STATUS
    root = ET.fromstring(builder().render(data(), mode, freeze_at=7.5))
    colors = {'accepted': STATUS['good'], 'rejected': STATUS['critical'],
              'duplicate': CATEGORICAL['violet'][mode]}
    chips = root.findall('.//s:g[@class="bid-chip"]', NS)
    travelers = root.findall('.//s:g[@class="traveler"]', NS)
    assert len(chips) == len(travelers) == len(data()['requests'])
    for row, chip, traveler in zip(data()['requests'], chips, travelers):
        for mark in (chip, traveler):
            rect = mark.find('s:rect', NS)
            assert rect.attrib['stroke'] == colors[row['outcome']]
            assert rect.attrib['fill'] == colors[row['outcome']]
            if row['outcome'] == 'accepted':
                assert float(rect.attrib['fill-opacity']) == 0.15
            assert all(label.attrib['fill'] == INK[mode] for label in mark.findall('s:g', NS))


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_accepted_log_cells_use_good_strokes_and_tints_opened_stays_neutral(mode):
    from figkit.color import INK, MUTED, STATUS
    root = ET.fromstring(builder().render(data(), mode))
    cells = root.findall('.//s:g[@class="log-cell"]', NS)
    for event, cell in zip(data()['events'], cells):
        rect = cell.find('s:rect', NS)
        if event['type'] == 'bid_accepted':
            assert rect.attrib['stroke'] == rect.attrib['fill'] == STATUS['good']
            assert float(rect.attrib['fill-opacity']) == 0.15
            assert cell.find('s:g', NS).attrib['fill'] == STATUS['good']
        else:
            assert rect.attrib['stroke'] == rect.attrib['fill'] == MUTED[mode]
            assert float(rect.attrib['fill-opacity']) == 0.08
            assert all(label.attrib['fill'] in (INK[mode], MUTED[mode])
                       for label in cell.findall('s:g', NS))


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_rejection_and_returned_labels_match_outcome_colors(mode):
    from figkit.color import CATEGORICAL, MUTED, STATUS
    root = ET.fromstring(builder().render(data(), mode))
    for name, color in [('rejection', STATUS['critical']),
                        ('duplicate', CATEGORICAL['violet'][mode])]:
        labels = root.find(f'.//s:g[@class="{name}"]', NS).findall('s:g', NS)
        assert labels[0].attrib['fill'] == color
        assert labels[1].attrib['fill'] == MUTED[mode]

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
    assert '@keyframes' not in svg
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

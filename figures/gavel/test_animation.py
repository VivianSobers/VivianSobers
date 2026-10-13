import json
import re
import xml.etree.ElementTree as ET

import pytest

from figures.gavel import build

NS = {'s': 'http://www.w3.org/2000/svg'}


def data():
    return json.loads((build.HERE / 'data.json').read_text())


def frames(css, name):
    block = re.search(r'@keyframes ' + name + r'\{((?:[^{}]*\{[^{}]*\})+)\}', css)
    assert block is not None
    return [(float(percent), rules) for percent, rules in
            re.findall(r'([0-9.]+)%\{([^{}]*)\}', block[1])]


def test_requests_arrive_serially_and_only_acceptances_reveal_cells():
    root = ET.fromstring(build.render(data(), 'light'))
    css = root.find('s:style', NS).text
    travelers = root.findall('.//s:g[@class="traveler"]', NS)
    assert [g.attrib['data-outcome'] for g in travelers] == ['rejected', 'accepted', 'accepted', 'duplicate']
    assert all('animation-delay:0.000s' in g.attrib['style'] for g in travelers)
    windows = []
    for index in range(4):
        visible = [p for p, rules in frames(css, f'travel{index}') if 'opacity:1' in rules]
        windows.append((min(visible), max(visible)))
    assert all(end < start for (_, end), (start, _) in zip(windows, windows[1:]))
    cells = root.findall('.//s:g[@class="log-cell"]', NS)
    assert 'style' not in cells[0].attrib
    assert 'append1' in cells[1].attrib['style']
    assert 'append2' in cells[2].attrib['style']
    assert len(cells) == 3
    assert not re.search(r'@keyframes append[03]\{', css)
    for index in (1, 2):
        reveal = next(p for p, rules in frames(css, f'append{index}') if 'opacity:1' in rules)
        assert windows[index][0] < reveal <= windows[index][1]
    assert all('14s ease-in-out infinite' in g.attrib['style'] for g in travelers)


def test_rejection_bounces_and_retry_returns_without_append():
    root = ET.fromstring(build.render(data(), 'dark'))
    css = root.find('s:style', NS).text
    movement = frames(css, 'travel0')
    assert any('translate(395px,75px)' in rules for _, rules in movement)
    assert any('translate(350px,75px)' in rules for _, rules in movement)
    assert 'append3' not in css
    rejection = root.find('.//s:g[@class="rejection"]', NS)
    duplicate = root.find('.//s:g[@class="duplicate"]', NS)
    assert 'reject0' in rejection.attrib['style']
    assert 'returned3' in duplicate.attrib['style']
    assert 'no new cell' in root.find('s:desc', NS).text


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_freeze_and_loop_reset_apply_to_every_animated_group(mode):
    root = ET.fromstring(build.render(data(), mode, freeze_at=9))
    css = root.find('s:style', NS).text
    animated = [g for g in root.findall('.//s:g', NS) if 'animation:' in g.attrib.get('style', '')]
    assert animated
    assert all('animation-delay:-9.000s' in g.attrib['style'] for g in animated)
    assert 'animation-play-state:paused!important' in css
    assert 'prefers-reduced-motion:reduce' in css
    for name in re.findall(r'@keyframes ([a-z0-9]+)', css):
        keyframes = frames(css, name)
        assert keyframes[0][0] == 0
        assert keyframes[-1][0] == 100
        assert keyframes[0][1] == keyframes[-1][1]

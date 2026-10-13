from figures.qk.test_build import NS, builder, data
import re
import xml.etree.ElementTree as ET

import pytest


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_motion_uses_each_heads_recorded_stops_and_layer_delay(mode):
    build = builder()
    snapshot = data()
    root = ET.fromstring(build.render(snapshot, mode, freeze_at=4))
    dots = root.findall('.//s:circle[@class="head"]', NS)
    for dot, row in zip(dots, snapshot['rows']):
        style = dot.attrib['style']
        for form in ('plain', 'no_rope'):
            offset = float(re.search(rf'--{form}:([-\d.]+)px', style)[1])
            assert float(dot.attrib['cx']) + offset == pytest.approx(build.log_x(row[form]), abs=0.02)
        assert f'animation-delay:{row["layer"] * 0.02 - 4:.3f}s' in style
    css = root.find('s:style', NS).text
    assert '16s ease-in-out infinite backwards' in css
    for fragment in ('0%,12.5%{transform:translateX(var(--plain))}',
                     '21.875%,34.375%{transform:translateX(var(--no_rope))}',
                     '43.75%,93.75%{transform:translateX(0)}'):
        assert fragment in css
    from figkit.color import BLUE, EMBER
    assert f'0%,34.375%{{fill:{EMBER[mode]};opacity:0.85}}' in css
    assert f'43.75%,87.5%{{fill:{BLUE[mode]};opacity:0.85}}' in css
    assert f'93.75%{{fill:{BLUE[mode]};opacity:0}}' in css
    assert '*{animation-play-state:paused!important}' in css
    assert '@media (prefers-reduced-motion:reduce){*{animation:none!important}}' in css


def test_trails_build_as_each_stop_is_left_and_reset_while_heads_are_hidden():
    root = ET.fromstring(builder().render(data(), 'light', freeze_at=6))
    css = root.find('s:style', NS).text
    assert '@keyframes trail_plain{0%,12.5%{opacity:0}21.875%,87.5%{opacity:0.3}93.75%,100%{opacity:0}}' in css
    assert '@keyframes trail_no_rope{0%,34.375%{opacity:0}43.75%,87.5%{opacity:0.3}93.75%,100%{opacity:0}}' in css
    for form in ('plain', 'no_rope'):
        traces = root.findall(f'.//s:circle[@class="trace {form}"]', NS)
        for trace, row in zip(traces, data()['rows']):
            assert f'animation-delay:{row["layer"] * 0.02 - 6:.3f}s' in trace.attrib['style']


def test_median_labels_highlight_the_active_stop():
    root = ET.fromstring(builder().render(data(), 'light', freeze_at=5))
    css = root.find('s:style', NS).text
    for form, hold in (('plain', '0%,12.5%,100%'), ('no_rope', '21.875%,34.375%'), ('exact', '43.75%,87.5%')):
        label = root.find(f'.//s:g[@class="label {form}"]', NS)
        assert label is not None
        assert label.attrib['opacity'] == '1'
        assert 'animation-delay:-5.000s' in label.attrib['style']
        assert f'@keyframes label_{form}' in css
        assert f'{hold}{{opacity:1}}' in css

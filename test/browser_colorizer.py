"""Run against a disposable Redmine with this plugin installed (see README)."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

base = os.environ["REDMINE_URL"].rstrip("/")
project = os.environ["REDMINE_PROJECT"]
screenshots = os.environ.get("SCREENSHOT_DIR")


def handlers(page):
    return page.evaluate("""() => {
      const counts = {};
      for (const [label, target] of [['document', document], ['window', window]]) {
        for (const [type, events] of Object.entries($._data(target, 'events') || {})) {
          const count = events.filter(e => e.namespace.split('.').includes('spectrum')).length;
          if (count) counts[label + ':' + type] = count;
        }
      }
      return counts;
    }""")


def select_text(area, text="Selected text", start=0, end=8):
    area.fill(text)
    area.evaluate("(e, range) => e.setSelectionRange(...range)", [start, end])


with sync_playwright() as p:
    launch = {"headless": True}
    if os.environ.get("CHROMIUM_PATH"):
        launch["executable_path"] = os.environ["CHROMIUM_PATH"]
    browser = p.chromium.launch(**launch)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors, failures = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda r: failures.append([r.status, r.url]) if r.status >= 400 else None)
    page.goto(base + "/login")
    page.locator("#username").fill(os.environ["REDMINE_USERNAME"])
    page.locator("#password").fill(os.environ["REDMINE_PASSWORD"])
    page.locator('input[name="login"]').click()
    page.goto(base + f"/projects/{project}/wiki/Wiki/edit")
    area = page.locator("#content_text")
    expect(area).to_be_visible()
    assert "Redmine" in page.title() or "Wiki" in page.title()
    button = page.locator("button.jstb_text_color")
    bg_button = page.locator("button.jstb_text_bgcolor")
    baseline = handlers(page)

    # No mouse hover: native keyboard activation must open a usable palette.
    select_text(area)
    button.focus()
    button.press("Enter")
    palette = page.locator(".sp-container:not(.sp-hidden)")
    expect(palette).to_be_visible()
    if screenshots:
        Path(screenshots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(screenshots) / "colorizer-palette-desktop.png"))
    swatch = palette.locator('.sp-thumb-el[data-color="rgb(244, 67, 54)"]').first
    swatch.focus()
    swatch.press("Enter")
    expect(area).to_have_value("<span style=color:#f44336;>Selected</span> text")
    assert handlers(page) == baseline

    # Applying the remembered color must work even when Spectrum sees no change.
    for _ in range(3):
        select_text(area)
        button.hover()
        palette.locator('.sp-thumb-el[data-color="rgb(244, 67, 54)"]').first.click()
        expect(area).to_have_value("<span style=color:#f44336;>Selected</span> text")
        assert page.locator(".sp-container").count() == 0
        assert handlers(page) == baseline

    # The initial black color is also a valid explicit choice.
    select_text(area)
    button.focus()
    button.press("Enter")
    palette.locator('.sp-thumb-el[data-color="rgb(0, 0, 0)"]').first.click()
    expect(area).to_have_value("<span style=color:black;>Selected</span> text")

    # Default background color, Space activation, and cancellation without edits.
    select_text(area)
    bg_button.focus()
    bg_button.press("Enter")
    swatch = palette.locator('.sp-thumb-el[data-color="rgb(255, 255, 255)"]').first
    swatch.focus()
    swatch.press("Space")
    expect(area).to_have_value("<span style=background-color:white;>Selected</span> text")
    before = area.input_value()
    bg_button.focus()
    bg_button.press("Enter")
    page.keyboard.press("Escape")
    expect(area).to_have_value(before)
    expect(bg_button).to_be_focused()
    assert handlers(page) == baseline

    # Moving away and clicking outside must dispose handlers without applying.
    button.hover()
    area.click()
    expect(area).to_have_value(before)
    assert page.locator(".sp-container").count() == 0
    assert handlers(page) == baseline

    # Empty selections should place the caret inside the generated span.
    select_text(area, "abcd", 2, 2)
    button.focus()
    button.press("Enter")
    palette.locator('.sp-thumb-el[data-color="rgb(0, 0, 0)"]').first.click()
    expect(area).to_have_value("ab<span style=color:black;></span>cd")
    assert area.evaluate("e => e.selectionStart") == len("ab<span style=color:black;>")
    assert area.evaluate("e => e.selectionEnd") == len("ab<span style=color:black;>")

    # Verify repeated AJAX previews retain supported CSS and remove unsafe HTML.
    area.fill('<span style=color:red;background-color:yellow;>Preview color</span><img src=x onerror=alert(1)>')
    for _ in range(2):
        page.locator("a.tab-preview").click()
        colored = page.locator(".wiki-preview span", has_text="Preview color")
        expect(colored).to_be_visible()
        expect(colored).to_have_css("color", "rgb(255, 0, 0)")
        expect(colored).to_have_css("background-color", "rgb(255, 255, 0)")
        assert page.locator(".wiki-preview [onerror]").count() == 0
        page.locator("a.tab-edit").click()

    # Dynamically created toolbars get their own picker and target textarea.
    page.evaluate("""() => {
      const area = document.createElement('textarea');
      area.id = 'colorizer_dynamic_editor';
      document.querySelector('#content').append(area);
      new jsToolBar(area).draw();
    }""")
    dynamic = page.locator("#colorizer_dynamic_editor")
    select_text(dynamic)
    dynamic_button = page.locator(".jstBlock").filter(has=dynamic).locator("button.jstb_text_color")
    dynamic_button.focus()
    dynamic_button.press("Enter")
    palette.locator('.sp-thumb-el[data-color="rgb(0, 0, 0)"]').first.click()
    expect(dynamic).to_have_value("<span style=color:black;>Selected</span> text")
    assert handlers(page) == baseline
    if screenshots:
        Path(screenshots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(screenshots) / "colorizer-desktop.png"))

    # Save the wiki and verify the normal display path, then the issue editor.
    area.fill('<span style=color:red;background-color:yellow;>Saved color</span>')
    page.get_by_role("button", name="Save", exact=True).click()
    saved = page.locator(".wiki span", has_text="Saved color")
    expect(saved).to_be_visible()
    expect(saved).to_have_css("color", "rgb(255, 0, 0)")
    expect(saved).to_have_css("background-color", "rgb(255, 255, 0)")
    page.goto(base + f"/projects/{project}/issues/new")
    issue_area = page.locator("#issue_description")
    select_text(issue_area)
    issue_button = page.locator(".jstBlock").filter(has=issue_area).locator("button.jstb_text_color")
    issue_button.focus()
    issue_button.press("Enter")
    palette.locator('.sp-thumb-el[data-color="rgb(244, 67, 54)"]').first.click()
    expect(issue_area).to_have_value("<span style=color:#f44336;>Selected</span> text")

    # Touch devices cannot rely on a mouseover event to initialize Spectrum.
    mobile = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True,
                                 storage_state=page.context.storage_state())
    touch = mobile.new_page()
    touch.on("pageerror", lambda e: errors.append(str(e)))
    touch.goto(base + f"/projects/{project}/wiki/Wiki/edit")
    touch_area = touch.locator("#content_text")
    select_text(touch_area)
    touch.locator("button.jstb_text_color").tap()
    touch.locator('.sp-container:not(.sp-hidden) .sp-thumb-el[data-color="rgb(244, 67, 54)"]').first.tap()
    expect(touch_area).to_have_value("<span style=color:#f44336;>Selected</span> text")
    if screenshots:
        touch.screenshot(path=str(Path(screenshots) / "colorizer-mobile.png"))
    assert not errors, errors
    # The deliberate missing img above is expected to 404 during preview.
    unexpected = [f for f in failures if not f[1].endswith('/x')]
    assert not unexpected, unexpected
    print(json.dumps({"url": page.url, "title": page.title(), "checks": "keyboard, pointer, touch, remembered/default colors, cancellation, cleanup, caret, preview, saved wiki, issue editor, sanitizer, dynamic toolbar", "errors": errors, "unexpected_http_failures": unexpected}))
    browser.close()

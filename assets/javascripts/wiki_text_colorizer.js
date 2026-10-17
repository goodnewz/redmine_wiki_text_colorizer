(() => {
  if (typeof jsToolBar === "undefined") return;

  const textFormatting = WikiTextColorizer["settings"]["textFormatting"];
  const textileCssOutput = WikiTextColorizer["settings"]["textileCssOutput"];
  const supportedTextFormatting = ["textile", "markdown", "common_mark"];

  if (!supportedTextFormatting.includes(textFormatting)) {
    // Unsupported text format
    return;
  }

  const resources = WikiTextColorizer["resources"] || {};
  resources.text = resources.text || {};

  /**
   * Add buttons to the jsToolBar.
   */
  function addButtonsToJsToolBar() {
    const textColorButton = {
      type: "text_color_button",
      title: resources.text.textColor,
      fn: {
        wiki: function (event) {
          event.stopPropagation();
          const jstbButton = $(this.toolbar).find(".jstb_text_color")[0];
          showColorPicker(jstbButton, true);
        },
      },
    };

    const textBGColorButton = {
      type: "text_color_button",
      title: resources.text.textBGColor,
      fn: {
        wiki: function (event) {
          event.stopPropagation();
          const jstbButton = $(this.toolbar).find(".jstb_text_bgcolor")[0];
          showColorPicker(jstbButton, true);
        },
      },
    };

    const jstbElements = {};
    for (const e in jsToolBar.prototype.elements) {
      jstbElements[e] = jsToolBar.prototype.elements[e];
      if (e === "del") {
        // Insert button to apply color to text after del
        jstbElements["text_color"] = textColorButton;
        jstbElements["text_bgcolor"] = textBGColorButton;
      }
    }
    jsToolBar.prototype.elements = jstbElements;

    jsToolBar.prototype.text_color_button = function (toolName) {
      const b = jsToolBar.prototype.button.call(this, toolName);
      const bDrawOrg = b.draw;
      b.draw = () => {
        const button = bDrawOrg.call(b);
        if (toolName === "text_color") {
          $(button).append($("<span/>").addClass("label").text("A"));
        } else {
          $(button).append(
            $("<div/>")
              .addClass("label-box")
              .append($("<span/>").addClass("label").text("A"))
          );
        }
        return button;
      };
      return b;
    };
  }
  addButtonsToJsToolBar();

  /**
   * Apply style to selected text of textarea
   * @param {*} jstbButton
   * @param {*} key
   * @param {*} value
   */
  function applyStyle(jstbButton, key, value) {
    const $textArea = $(jstbButton)
      .closest(".jstBlock")
      .find(".jstEditor > textarea");

    if ($textArea.length === 0) {
      console.warn("Textarea not found.");
      return false;
    }

    const textArea = $textArea[0];
    const text = textArea.value;
    const start = textArea.selectionStart;
    const end = textArea.selectionEnd;
    const selected = text.substring(start, end);
    const prefix =
      textFormatting === "textile" && textileCssOutput
        ? `%{${key}:${value}}`
        : `<span style=${key}:${value};>`;
    const suffix =
      textFormatting === "textile" && textileCssOutput ? "%" : "</span>";

    // Update textarea
    textArea.setRangeText(prefix + selected + suffix);

    // Move cursor
    if (start === end) {
      textArea.selectionStart = start + prefix.length;
    }

    // Postprocessing
    $textArea.change().focus();

    return true;
  }

  /**
   * Format text color or text background color of textarea with jstb button.
   * @param {*} jstbButton
   * @param {*} color
   */
  function formatTextColor(jstbButton, color, background = false) {
    if (!color) return;

    const colorString = color.toName() || color.toHexString();

    if (
      applyStyle(
        jstbButton,
        (background ? "background-" : "") + "color",
        colorString
      )
    ) {
      // Backup color string to button
      $(jstbButton).data("color", colorString);

      if (background) {
        $(jstbButton)
          .children("div.label-box")
          .css({
            backgroundColor: colorString,
            color: color.isDark() ? "#EEE" : "#111",
          });
      } else {
        $(jstbButton).children("span.label").css("color", colorString);
      }
    }
  }

  /** Keep Spectrum alive until it hides so its document handlers are removed. */
  function showColorPicker(button, focusPalette = false) {
    const $button = $(button);
    if ($button.data("spectrum.id") === undefined) {
      let applyOnHide = false;
      $button.spectrum({
        color: $button.data("color") ||
          ($button.hasClass("jstb_text_bgcolor") ? "white" : "black"),
        allowEmpty: false,
        clickoutFiresChange: false,
        togglePaletteOnly: true,
        showPaletteOnly: true,
        togglePaletteMoreText: resources.text.togglePaletteMoreText,
        togglePaletteLessText: resources.text.togglePaletteLessText,
        hideAfterPaletteSelect: true,
        showAlpha: false,
        showInput: true,
        localStorageKey: "wiki-text-colorizer-spectrum-selection-palette",
        change: function () {
          applyOnHide = true;
        },
        hide: function (color) {
          const restoreFocus = $palette[0].contains(document.activeElement);
          if (applyOnHide) {
            formatTextColor(this, color, $(this).hasClass("jstb_text_bgcolor"));
          }
          // Spectrum.hide unbinds document/window events before this callback.
          $(this).spectrum("destroy").attr("aria-expanded", "false");
          if (restoreFocus && !applyOnHide) this.focus();
        },
      });
      $button.attr("aria-haspopup", "dialog");
      const $palette = $button.spectrum("container");
      $palette.attr({role: "dialog", "aria-label": $button.attr("title")});
      // Choosing the initial/remembered color does not emit Spectrum's change.
      $palette[0].addEventListener("click", function (event) {
        if (event.target.closest(".sp-thumb-el")) applyOnHide = true;
      }, true);
      // Spectrum's bundled keyboard handler targets divs, but swatches are spans.
      $palette.on("keydown", ".sp-thumb-el", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          this.click();
        }
      });
    }
    $button.spectrum("show").attr("aria-expanded", "true");
    if (focusPalette) {
      $button.spectrum("container").find(".sp-thumb-el").first().trigger("focus");
    }
  }

  $(() => {
    // Delegation also supports toolbars added by AJAX after the page loads.
    $(document).on("mouseenter", ".jstb_text_color, .jstb_text_bgcolor", function () {
      showColorPicker(this);
    });
  });
})();

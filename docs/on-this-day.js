(function () {
  function formatDateLabel(date) {
    return date.toLocaleDateString(undefined, {
      month: "long",
      day: "numeric",
    });
  }

  async function initOnThisDay() {
    var headingEl = document.getElementById("on-this-day-heading");
    var subtitleEl = document.getElementById("on-this-day-subtitle");
    var containerEl = document.getElementById("on-this-day-entries");

    if (!containerEl) return;

    var today = new Date();
    var month = String(today.getMonth() + 1).padStart(2, "0");
    var day = String(today.getDate()).padStart(2, "0");
    var key = month + "-" + day;
    var label = formatDateLabel(today);

    if (headingEl) {
      headingEl.textContent = "On this day – " + label;
    }
    if (subtitleEl) {
      subtitleEl.textContent =
        "Entries from different years that happened on " + label + ".";
    }

    try {
      var resp = await fetch("on_this_day_index.json", { cache: "no-cache" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();

      var items = data[key] || [];
      if (!items.length) {
        containerEl.innerHTML = "<p>No earlier entries for this date yet.</p>";
        return;
      }

      containerEl.innerHTML = items
        .map(function (item) {
          return item.html;
        })
        .join("\n\n");
    } catch (err) {
      console.error("Failed to load On This Day index:", err);
      containerEl.innerHTML =
        "<p>Could not load entries for today. Please try again later.</p>";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOnThisDay);
  } else {
    initOnThisDay();
  }
})();

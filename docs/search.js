// search.js - client-side Lunr search for Rohit's Journal

// NOTE: expects lunr.min.js and search_index.json in the same directory as the HTML

(function () {
  var searchInput = document.getElementById("search-input");
  var resultsContainer = document.getElementById("search-results");
  if (!searchInput || !resultsContainer || typeof lunr === "undefined") {
    return;
  }

  var docs = [];
  var idx = null;

  function renderResults(results) {
    if (!results.length) {
      resultsContainer.innerHTML = "";
      return;
    }

    var html = '<ul class="search-results-list">';
    results.forEach(function (r) {
      var doc = docs.find(function (d) { return d.id === r.ref; });
      if (!doc) return;

      var snippet = doc.text;
      if (snippet.length > 200) {
        snippet = snippet.slice(0, 200) + "…";
      }

      html += (
        '<li class="search-result">' +
          '<a href="' + doc.url + '" class="search-result-title">' +
            doc.title +
          "</a>" +
          '<p class="search-result-snippet">' + snippet + "</p>" +
        "</li>"
      );
    });
    html += "</ul>";

    resultsContainer.innerHTML = html;
  }

  function initLunr() {
    fetch("search_index.json")
      .then(function (res) { return res.json(); })
      .then(function (data) {
        docs = data;

        idx = lunr(function () {
          this.ref("id");
          this.field("title");
          this.field("text");

          docs.forEach(function (doc) {
            this.add(doc);
          }, this);
        });
      })
      .catch(function (err) {
        console.error("Error loading search index:", err);
      });
  }

  searchInput.addEventListener("input", function (e) {
    var q = e.target.value.trim();
    if (!idx || !q) {
      resultsContainer.innerHTML = "";
      return;
    }

    var results = idx.search(q);
    renderResults(results);
  });

  initLunr();
})();

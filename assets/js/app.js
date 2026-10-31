/**
 * Tamil Nadu Politics Brief - Client-Side Application Engine
 * Handles edition rendering, archive filtering, client-side search, and theme persistence.
 */

const TN_PARTIES = [
    "DMK", "AIADMK", "BJP", "INC", "TVK", "PMK",
    "NTK", "VCK", "MDMK", "DMDK", "AMMK", "Left Parties"
];

const TN_TOPICS = [
    "Government & Administration",
    "Political Parties",
    "Assembly, Courts & Policy",
    "Elections",
    "Education & NEET",
    "Agriculture & Water",
    "Public Protests & Labour",
    "Centre–State Relations",
    "Infrastructure & Economy"
];

const TN_DISTRICTS = [
    "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri",
    "Dindigul", "Erode", "Kallakurichi", "Kancheepuram", "Kanniyakumari", "Karur",
    "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal", "Nilgiris",
    "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga",
    "Tenkasi", "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli",
    "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur", "Vellore",
    "Viluppuram", "Virudhunagar"
];

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function initTheme() {
    const saved = localStorage.getItem("tnpb_theme") || "light";
    document.documentElement.setAttribute("data-theme", saved);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
        btn.textContent = saved === "dark" ? "Light Mode" : "Dark Mode";
        btn.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("tnpb_theme", next);
            btn.textContent = next === "dark" ? "Light Mode" : "Dark Mode";
        });
    }
    const clockEl = document.getElementById("ist-date-display");
    if (clockEl) {
        const now = new Date();
        clockEl.textContent = now.toLocaleDateString("en-IN", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
            timeZone: "Asia/Kolkata"
        }) + " (IST)";
    }
}

function renderEditionCard(ed, slotLabel) {
    if (!ed) {
        return `
      <div class="card">
        <div class="card-kicker">${escapeHtml(slotLabel)}</div>
        <h3>Edition Awaiting Scheduled Run</h3>
        <p class="meta-line">Target schedule: 6:00 AM / 6:00 PM IST via GitHub Actions.</p>
        <p>No edition has been published for this slot yet.</p>
      </div>
    `;
    }
    const sampleBadge = ed.is_test_sample
        ? `<span class="badge badge-warn">SAMPLE TEST DATA</span>`
        : `<span class="badge badge-verified">${escapeHtml(ed.status.toUpperCase())}</span>`;

    const partyBadges = (ed.parties || [])
        .slice(0, 6)
        .map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`)
        .join("");

    return `
    <article class="card">
      <div class="card-kicker">${escapeHtml(slotLabel)} &bull; ${escapeHtml(ed.date)}</div>
      <div style="margin-bottom:0.5rem;">${sampleBadge}</div>
      <h2><a href="${escapeHtml(ed.url)}">${escapeHtml(ed.headline)}</a></h2>
      <p class="meta-line">
        Published: ${escapeHtml(ed.published_at_ist)} &bull;
        Reading time: ~${escapeHtml(ed.reading_time_minutes)} min
      </p>
      <p style="margin-bottom:0.85rem;">${escapeHtml(ed.big_picture_excerpt || "")}</p>
      <div style="margin-bottom:0.85rem;">${partyBadges}</div>
      <a href="${escapeHtml(ed.url)}" style="font-family:var(--font-sans);font-weight:600;font-size:0.9rem;">
        Read Full Briefing &rarr;
      </a>
    </article>
  `;
}

function renderFullEditionView(container, ed) {
    const sec = ed.sections || {};
    const sampleBanner = ed.is_test_sample
        ? `<div class="status-banner sample-warning">
         SAMPLE TEST DATA NOTICE: This edition is clearly marked test verification data and does not represent live political news.
       </div>`
        : "";

    const devsHtml = (sec.top_developments || []).map((d, i) => {
        const srcLinks = (d.sources || []).map(s =>
            `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.publisher)}: ${escapeHtml(s.title)} (${escapeHtml(s.language.toUpperCase())})</a>`
        ).join(" &bull; ");

        return `
      <div class="story-item">
        <span class="badge badge-verified">${escapeHtml(d.verification_badge || "Verified")}</span>
        <h3>${i + 1}. ${escapeHtml(d.headline)}</h3>
        <div class="story-field"><strong>What happened?</strong> ${escapeHtml(d.what_happened)}</div>
        <div class="story-field"><strong>Who is involved?</strong> ${escapeHtml(d.who_is_involved)}</div>
        <div class="story-field"><strong>Verified facts:</strong> ${escapeHtml(d.verified_facts)}</div>
        <div class="story-field"><strong>Why does it matter?</strong> ${escapeHtml(d.why_it_matters)}</div>
        <div class="story-field"><strong>Political responses:</strong> ${escapeHtml(d.political_responses)}</div>
        <div class="story-field"><strong>What happens next?</strong> ${escapeHtml(d.what_happens_next)}</div>
        <div class="story-field" style="margin-top:0.75rem;font-family:var(--font-sans);font-size:0.84rem;">
          <strong>Original Sources:</strong> ${srcLinks || "None"}
        </div>
      </div>
    `;
    }).join("");

    const claimsHtml = (sec.claims_vs_facts || []).map(c => `
    <div class="story-item">
      <div class="story-field"><strong>Claim (${escapeHtml(c.claimant)}):</strong> ${escapeHtml(c.claim)}</div>
      <div class="story-field"><strong>Verified Evidence:</strong> ${escapeHtml(c.verified_evidence)}</div>
    </div>
  `).join("") || "<p>No disputed political claims flagged in this coverage window.</p>";

    const sourcesHtml = (sec.all_sources || []).map(s => `
    <li style="margin-bottom:0.45rem;">
      <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.title)}</a>
      &mdash; <strong>${escapeHtml(s.publisher)}</strong> (${escapeHtml(s.published_date)}, ${escapeHtml(s.language.toUpperCase())})
    </li>
  `).join("");

    container.innerHTML = `
    ${sampleBanner}
    <div class="edition-layout">
      <aside class="toc-sidebar">
        <h4>Edition Contents</h4>
        <ul>
          <li><a href="#sec-a">A. Edition Info</a></li>
          <li><a href="#sec-b">B. The Big Picture</a></li>
          <li><a href="#sec-c">C. Top Developments</a></li>
          <li><a href="#sec-d">D. Government &amp; Admin</a></li>
          <li><a href="#sec-e">E. Political Parties</a></li>
          <li><a href="#sec-f">F. Assembly &amp; Courts</a></li>
          <li><a href="#sec-g">G. District Updates</a></li>
          <li><a href="#sec-h">H. Claims vs. Facts</a></li>
          <li><a href="#sec-i">I. What to Watch Next</a></li>
          <li><a href="#sec-j">J. Full Source List</a></li>
        </ul>
        <hr style="margin:0.85rem 0;border:none;border-top:1px solid var(--border-color);">
        <button onclick="window.print()" class="theme-btn" style="width:100%;">Print / Save PDF</button>
      </aside>
      <div class="reading-column">
        <section id="sec-a" class="section-block">
          <div class="card-kicker">${escapeHtml(ed.edition_type.toUpperCase())} EDITION &bull; ${escapeHtml(ed.date)}</div>
          <h1 style="font-size:2rem;line-height:1.25;margin:0.4rem 0 0.75rem;">${escapeHtml(ed.headline)}</h1>
          <p class="meta-line">
            <strong>Edition Title:</strong> ${escapeHtml(ed.title)}<br>
            <strong>Coverage Window:</strong> ${escapeHtml(ed.coverage_start_ist)} to ${escapeHtml(ed.coverage_end_ist)}<br>
            <strong>Generated:</strong> ${escapeHtml(ed.generated_at_ist)} &bull;
            <strong>Published:</strong> ${escapeHtml(ed.published_at_ist)} &bull;
            <strong>Status:</strong> ${escapeHtml(ed.status)} &bull;
            <strong>Reading Time:</strong> ~${escapeHtml(ed.reading_time_minutes)} min
          </p>
        </section>

        <section id="sec-b" class="section-block">
          <h2>B. The Big Picture</h2>
          <p>${escapeHtml(sec.big_picture)}</p>
        </section>

        <section id="sec-c" class="section-block">
          <h2>C. Top Political Developments</h2>
          ${devsHtml || "<p>No major verified developments recorded in this window.</p>"}
        </section>

        <section id="sec-d" class="section-block">
          <h2>D. Government and Administration</h2>
          <p>${escapeHtml(sec.government_and_administration)}</p>
        </section>

        <section id="sec-e" class="section-block">
          <h2>E. Political Parties and Opposition</h2>
          <p>${escapeHtml(sec.political_parties_and_opposition)}</p>
        </section>

        <section id="sec-f" class="section-block">
          <h2>F. Assembly, Courts, and Policy</h2>
          <p>${escapeHtml(sec.assembly_courts_and_policy)}</p>
        </section>

        <section id="sec-g" class="section-block">
          <h2>G. District-Level Developments</h2>
          <p>${escapeHtml(sec.district_developments)}</p>
        </section>

        <section id="sec-h" class="section-block">
          <h2>H. Claims Versus Verified Facts</h2>
          ${claimsHtml}
        </section>

        <section id="sec-i" class="section-block">
          <h2>I. What to Watch Next</h2>
          <p>${escapeHtml(sec.what_to_watch_next)}</p>
        </section>

        <section id="sec-j" class="section-block">
          <h2>J. Sources and Further Reading</h2>
          <ul style="padding-left:1.2rem;">${sourcesHtml || "<li>No external links in this window.</li>"}</ul>
        </section>
      </div>
    </div>
  `;
}

async function initHomePage() {
    const statusEl = document.getElementById("system-status-banner");
    const cardsEl = document.getElementById("latest-editions-grid");
    const inlineEditionEl = document.getElementById("lead-edition-preview");
    if (!cardsEl) return;

    try {
        const res = await fetch("data/latest-editions.json");
        const data = await res.json();

        if (statusEl) {
            statusEl.textContent = data.status_message || "Automated twice-daily publishing active.";
        }

        cardsEl.innerHTML =
            renderEditionCard(data.morning, "Morning Brief (6:00 AM IST)") +
            renderEditionCard(data.evening, "Evening Brief (6:00 PM IST)");

        const mostRecent = data.evening || data.morning;
        if (mostRecent && mostRecent.json_path && inlineEditionEl) {
            const edRes = await fetch(mostRecent.json_path);
            const edFull = await edRes.json();
            renderFullEditionView(inlineEditionEl, edFull);
        }
    } catch (err) {
        cardsEl.innerHTML = `<div class="card"><p>Unable to load latest editions metadata: ${escapeHtml(err.message)}</p></div>`;
    }
}

async function initEditionPage() {
    const container = document.getElementById("full-edition-container");
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const editionId = params.get("id");

    try {
        const idxRes = await fetch("data/archive-index.json");
        const idxData = await idxRes.json();
        const editions = idxData.editions || [];
        const target = editionId
            ? editions.find(e => e.edition_id === editionId)
            : editions[0];

        if (!target) {
            container.innerHTML = `<div class="card"><h2>Edition Not Found</h2><p>Requested edition ID "${escapeHtml(editionId)}" does not exist in the historical archive.</p></div>`;
            return;
        }

        const edRes = await fetch(target.json_path);
        const edData = await edRes.json();
        document.title = `${edData.title} | Tamil Nadu Politics Brief`;
        renderFullEditionView(container, edData);
    } catch (err) {
        container.innerHTML = `<div class="card"><p>Error loading edition: ${escapeHtml(err.message)}</p></div>`;
    }
}

function populateSelect(selectEl, items, defaultLabel) {
    if (!selectEl) return;
    selectEl.innerHTML = `<option value="">${escapeHtml(defaultLabel)}</option>` +
        items.map(i => `<option value="${escapeHtml(i)}">${escapeHtml(i)}</option>`).join("");
}

async function initArchivePage() {
    const listEl = document.getElementById("archive-results");
    if (!listEl) return;

    const dateInput = document.getElementById("filter-date");
    const typeSelect = document.getElementById("filter-type");
    const partySelect = document.getElementById("filter-party");
    const topicSelect = document.getElementById("filter-topic");
    const districtSelect = document.getElementById("filter-district");

    populateSelect(partySelect, TN_PARTIES, "All Political Parties");
    populateSelect(topicSelect, TN_TOPICS, "All Topics");
    populateSelect(districtSelect, TN_DISTRICTS, "All 38 Districts");

    const res = await fetch("data/archive-index.json");
    const data = await res.json();
    const allEditions = data.editions || [];

    function applyFilters() {
        const fDate = dateInput ? dateInput.value : "";
        const fType = typeSelect ? typeSelect.value : "";
        const fParty = partySelect ? partySelect.value : "";
        const fTopic = topicSelect ? topicSelect.value : "";
        const fDistrict = districtSelect ? districtSelect.value : "";

        const filtered = allEditions.filter(ed => {
            if (fDate && ed.date !== fDate) return false;
            if (fType && ed.edition_type !== fType) return false;
            if (fParty && !(ed.parties || []).includes(fParty)) return false;
            if (fTopic && !(ed.topics || []).includes(fTopic)) return false;
            if (fDistrict && !(ed.districts || []).includes(fDistrict)) return false;
            return true;
        });

        if (!filtered.length) {
            listEl.innerHTML = `<div class="card"><p>No archived editions match the selected filters.</p></div>`;
            return;
        }

        listEl.innerHTML = filtered.map(ed => `
      <article class="card" style="margin-bottom:1rem;">
        <div class="card-kicker">${escapeHtml(ed.date)} &bull; ${escapeHtml(ed.edition_type.toUpperCase())} EDITION</div>
        <h3><a href="${escapeHtml(ed.url)}">${escapeHtml(ed.headline)}</a></h3>
        <p class="meta-line">Coverage: ${escapeHtml(ed.coverage_window)} &bull; ~${escapeHtml(ed.reading_time_minutes)} min read</p>
        <p style="margin-bottom:0.65rem;">${escapeHtml(ed.summary_text)}</p>
        <div>
          ${(ed.parties || []).map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`).join("")}
          ${(ed.districts || []).map(d => `<span class="badge badge-tag">${escapeHtml(d)}</span>`).join("")}
        </div>
      </article>
    `).join("");
    }

    [dateInput, typeSelect, partySelect, topicSelect, districtSelect].forEach(el => {
        if (el) el.addEventListener("input", applyFilters);
    });

    applyFilters();
}

async function initSearchPage() {
    const inputEl = document.getElementById("search-query-input");
    const resultsEl = document.getElementById("search-results-list");
    if (!inputEl || !resultsEl) return;

    const res = await fetch("data/archive-index.json");
    const data = await res.json();
    const editions = data.editions || [];

    function runSearch() {
        const q = inputEl.value.trim().toLowerCase();
        if (!q) {
            resultsEl.innerHTML = `<p class="meta-line">Enter a keyword above (e.g., DMK, AIADMK, TVK, BJP, NEET, Assembly, Cauvery, Chennai, Madurai) to search all historical briefings.</p>`;
            return;
        }

        const matches = editions.filter(ed => {
            const haystack = [
                ed.title,
                ed.headline,
                ed.summary_text,
                ...(ed.parties || []),
                ...(ed.topics || []),
                ...(ed.districts || [])
            ].join(" ").toLowerCase();
            return haystack.includes(q);
        });

        if (!matches.length) {
            resultsEl.innerHTML = `<div class="card"><p>No historical editions found matching "<strong>${escapeHtml(q)}</strong>".</p></div>`;
            return;
        }

        resultsEl.innerHTML = `<p class="meta-line">Found ${matches.length} edition(s) matching "${escapeHtml(q)}":</p>` +
            matches.map(ed => `
        <article class="card" style="margin-bottom:1rem;">
          <div class="card-kicker">${escapeHtml(ed.date)} &bull; ${escapeHtml(ed.edition_type.toUpperCase())}</div>
          <h3><a href="${escapeHtml(ed.url)}">${escapeHtml(ed.headline)}</a></h3>
          <p style="margin-bottom:0.5rem;">${escapeHtml(ed.summary_text)}</p>
          <a href="${escapeHtml(ed.url)}">Open Permanent Edition &rarr;</a>
        </article>
      `).join("");
    }

    inputEl.addEventListener("input", runSearch);
    document.querySelectorAll(".quick-chip").forEach(btn => {
        btn.addEventListener("click", () => {
            inputEl.value = btn.getAttribute("data-keyword");
            runSearch();
        });
    });
    runSearch();
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initHomePage();
    initEditionPage();
    initArchivePage();
    initSearchPage();
});
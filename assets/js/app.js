/**
 * Tamil Nadu Politics Brief - Clean Newspaper UI Engine
 * Removes repetitive Q&A labels and formats all timestamps into readable IST.
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

function formatReadableIST(isoStr) {
    if (!isoStr) return "";
    const dt = new Date(isoStr);
    if (isNaN(dt.getTime())) return escapeHtml(isoStr);
    return dt.toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
        timeZone: "Asia/Kolkata"
    }) + " IST";
}

function formatStatusLabel(status) {
    const map = {
        "published": "Verified Edition",
        "published_delayed": "Published Edition",
        "published_quiet_window": "Quiet Window",
        "published_extractive_fallback": "Live Feed Edition"
    };
    return map[status] || "Published Edition";
}

function formatEditorialText(str) {
    if (!str) return "";
    const escaped = escapeHtml(str);
    const formattedBold = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    return formattedBold
        .split(/\n{2,}/)
        .map(block => {
            const lines = block.trim().split("\n");
            const isBulletList = lines.every(line => /^[-*•]\s+/.test(line.trim()));
            if (isBulletList) {
                const items = lines
                    .map(line => `<li>${line.trim().replace(/^[-*•]\s+/, "")}</li>`)
                    .join("");
                return `<ul style="padding-left:1.25rem;margin-bottom:0.85rem;">${items}</ul>`;
            }
            return `<p style="margin-bottom:0.85rem;">${lines.join("<br>")}</p>`;
        })
        .join("");
}

function shareOnWhatsApp(editionId, headline) {
    const baseUrl = window.location.origin + window.location.pathname.replace(/[^/]*$/, "");
    const fullUrl = `${baseUrl}edition.html?id=${encodeURIComponent(editionId)}`;
    const text = `${headline} — Read on Tamil Nadu Politics Brief: ${fullUrl}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
}

function copyEditionLink(editionId) {
    const baseUrl = window.location.origin + window.location.pathname.replace(/[^/]*$/, "");
    const fullUrl = `${baseUrl}edition.html?id=${encodeURIComponent(editionId)}`;
    if (navigator.clipboard) {
        navigator.clipboard.writeText(fullUrl);
        alert("Edition link copied to clipboard!");
    }
}

function initTheme() {
    const saved = localStorage.getItem("tnpb_theme") || "dark";
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
        clockEl.textContent = new Date().toLocaleDateString("en-IN", {
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
    const badge = ed.is_test_sample
        ? `<span class="badge badge-warn">SAMPLE TEST DATA</span>`
        : `<span class="badge badge-verified">${escapeHtml(formatStatusLabel(ed.status))}</span>`;

    const partyBadges = (ed.parties || [])
        .slice(0, 6)
        .map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`)
        .join("");

    return `
    <article class="card">
      <div class="card-kicker">${escapeHtml(slotLabel)} &bull; ${escapeHtml(ed.date)}</div>
      <div style="margin-bottom:0.5rem;">${badge}</div>
      <h2><a href="${escapeHtml(ed.url)}">${escapeHtml(ed.headline)}</a></h2>
      <p class="meta-line">
        Updated: ${formatReadableIST(ed.published_at_ist)} &bull; ~${escapeHtml(ed.reading_time_minutes)} min read
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

    const devsHtml = (sec.top_developments || []).map((d, i) => {
        const rawBody = (d.summary || d.what_happened || "").trim();
        const headlineClean = (d.headline || "").trim();

        // Never repeat the headline as the body text if the RSS snippet was identical to the title
        const hasDistinctBody = rawBody && rawBody.toLowerCase() !== headlineClean.toLowerCase();

        const seenUrls = new Set();
        const uniqueSources = (d.sources || []).filter(s => {
            if (!s.url || seenUrls.has(s.url)) return false;
            seenUrls.add(s.url);
            return true;
        });

        const srcLinks = uniqueSources.map(s =>
            `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.publisher)}: ${escapeHtml(s.title)}</a>`
        ).join(" &bull; ");

        // Show clean Context tags only if useful and non-generic
        const involved = d.who_is_involved && d.who_is_involved !== "State Administration / Public Stakeholders"
            ? `<span class="badge badge-tag">${escapeHtml(d.who_is_involved)}</span>`
            : "";

        const whyMatters = d.why_it_matters && !d.why_it_matters.startsWith("Affects ") && !d.why_it_matters.startsWith("Relates to ")
            ? `<p style="border-left:3px solid var(--accent-blue);padding-left:0.75rem;margin:0.65rem 0;color:var(--text-secondary);font-size:0.95rem;"><strong>Why it matters:</strong> ${escapeHtml(d.why_it_matters)}</p>`
            : "";

        return `
      <article class="story-item">
        <div style="margin-bottom:0.45rem;">
          <span class="badge badge-verified">${escapeHtml(d.verification_badge || "Verified Report")}</span>
          ${involved}
        </div>
        <h3 style="margin-bottom:0.6rem;">${i + 1}. ${escapeHtml(headlineClean)}</h3>
        ${hasDistinctBody ? `<div style="margin-bottom:0.65rem;">${formatEditorialText(rawBody)}</div>` : ""}
        ${whyMatters}
        <div class="meta-line" style="margin-bottom:0;padding-top:0.4rem;border-top:1px solid var(--border-color);">
          <strong>Source:</strong> ${srcLinks || "Official feed"}
        </div>
      </article>
    `;
    }).join("");

    const claimsHtml = (sec.claims_vs_facts || []).map(c => `
    <div class="story-item">
      <div class="story-field"><strong>Claim (${escapeHtml(c.claimant)}):</strong> ${escapeHtml(c.claim)}</div>
      <div class="story-field"><strong>Verified Evidence:</strong> ${escapeHtml(c.verified_evidence)}</div>
    </div>
  `).join("") || "<p>No disputed partisan claims flagged in this window.</p>";

    const sourcesHtml = (sec.all_sources || []).map(s => `
    <li style="margin-bottom:0.45rem;">
      <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.title)}</a>
      &mdash; <strong>${escapeHtml(s.publisher)}</strong> (${escapeHtml(s.published_date)})
    </li>
  `).join("");

    container.innerHTML = `
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
        <button onclick="shareOnWhatsApp('${escapeHtml(ed.edition_id)}', '${escapeHtml(ed.headline.replace(/'/g, "\\'"))}')" class="theme-btn" style="width:100%;background:#1f8b4c;color:#fff;border:none;padding:0.5rem;margin-bottom:0.45rem;font-weight:600;">Share on WhatsApp</button>
        <button onclick="copyEditionLink('${escapeHtml(ed.edition_id)}')" class="theme-btn" style="width:100%;padding:0.45rem;margin-bottom:0.45rem;">Copy Edition Link</button>
        <button onclick="window.print()" class="theme-btn" style="width:100%;padding:0.45rem;">Print / Save PDF</button>
      </aside>
      <div class="reading-column">
        <section id="sec-a" class="section-block">
          <div class="card-kicker">${escapeHtml(ed.edition_type.toUpperCase())} EDITION &bull; ${escapeHtml(ed.date)}</div>
          <h1 style="font-size:2rem;line-height:1.25;margin:0.4rem 0 0.75rem;">${escapeHtml(ed.headline)}</h1>
          <p class="meta-line">
            <strong>Edition:</strong> ${escapeHtml(ed.title)}<br>
            <strong>Coverage Window:</strong> ${formatReadableIST(ed.coverage_start_ist)} &ndash; ${formatReadableIST(ed.coverage_end_ist)}<br>
            <strong>Published:</strong> ${formatReadableIST(ed.published_at_ist)} &bull;
            <strong>Reading Time:</strong> ~${escapeHtml(ed.reading_time_minutes)} min
          </p>
        </section>

        <section id="sec-b" class="section-block">
          <h2>B. The Big Picture</h2>
          ${formatEditorialText(sec.big_picture)}
        </section>

        <section id="sec-c" class="section-block">
          <h2>C. Top Political Developments</h2>
          ${devsHtml || "<p>No major verified developments recorded in this window.</p>"}
        </section>

        <section id="sec-d" class="section-block">
          <h2>D. Government and Administration</h2>
          ${formatEditorialText(sec.government_and_administration)}
        </section>

        <section id="sec-e" class="section-block">
          <h2>E. Political Parties and Opposition</h2>
          ${formatEditorialText(sec.political_parties_and_opposition)}
        </section>

        <section id="sec-f" class="section-block">
          <h2>F. Assembly, Courts, and Policy</h2>
          ${formatEditorialText(sec.assembly_courts_and_policy)}
        </section>

        <section id="sec-g" class="section-block">
          <h2>G. District-Level Developments</h2>
          ${formatEditorialText(sec.district_developments)}
        </section>

        <section id="sec-h" class="section-block">
          <h2>H. Claims Versus Verified Facts</h2>
          ${claimsHtml}
        </section>

        <section id="sec-i" class="section-block">
          <h2>I. What to Watch Next</h2>
          ${formatEditorialText(sec.what_to_watch_next)}
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
        const res = await fetch("data/latest-editions.json", { cache: "no-store" });
        const data = await res.json();

        if (statusEl) {
            statusEl.textContent = `Latest edition updated on ${formatReadableIST(data.last_updated_ist)}`;
        }

        cardsEl.innerHTML =
            renderEditionCard(data.morning, "Morning Brief (6:00 AM IST)") +
            renderEditionCard(data.evening, "Evening Brief (6:00 PM IST)");

        let mostRecent = null;
        if (data.evening && data.morning) {
            if (data.evening.date > data.morning.date) {
                mostRecent = data.evening;
            } else if (data.morning.date > data.evening.date) {
                mostRecent = data.morning;
            } else {
                mostRecent = data.evening;
            }
        } else {
            mostRecent = data.evening || data.morning;
        }
        if (mostRecent && mostRecent.json_path && inlineEditionEl) {
            const edRes = await fetch(mostRecent.json_path, { cache: "no-store" });
            const edFull = await edRes.json();
            renderFullEditionView(inlineEditionEl, edFull);
        }
    } catch (err) {
        cardsEl.innerHTML = `<div class="card"><p>Unable to load latest editions: ${escapeHtml(err.message)}</p></div>`;
    }
}

async function initEditionPage() {
    const container = document.getElementById("full-edition-container");
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const editionId = params.get("id");

    try {
        const idxRes = await fetch("data/archive-index.json", { cache: "no-store" });
        const idxData = await idxRes.json();
        const editions = idxData.editions || [];
        const target = editionId
            ? editions.find(e => e.edition_id === editionId)
            : editions[0];

        if (!target) {
            container.innerHTML = `<div class="card"><h2>Edition Not Found</h2></div>`;
            return;
        }

        const edRes = await fetch(target.json_path, { cache: "no-store" });
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

    const res = await fetch("data/archive-index.json", { cache: "no-store" });
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
        <p class="meta-line">Published: ${formatReadableIST(ed.published_at_ist)} &bull; ~${escapeHtml(ed.reading_time_minutes)} min read</p>
        <div>
          ${(ed.parties || []).map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`).join("")}
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

    const res = await fetch("data/archive-index.json", { cache: "no-store" });
    const data = await res.json();
    const editions = data.editions || [];

    function runSearch() {
        const q = inputEl.value.trim().toLowerCase();
        if (!q) {
            resultsEl.innerHTML = `<p class="meta-line">Enter a keyword above to search all historical briefings.</p>`;
            return;
        }

        const matches = editions.filter(ed => {
            const haystack = [
                ed.title, ed.headline, ed.summary_text,
                ...(ed.parties || []), ...(ed.topics || []), ...(ed.districts || [])
            ].join(" ").toLowerCase();
            return haystack.includes(q);
        });

        if (!matches.length) {
            resultsEl.innerHTML = `<div class="card"><p>No historical editions found matching "<strong>${escapeHtml(q)}</strong>".</p></div>`;
            return;
        }

        resultsEl.innerHTML = matches.map(ed => `
      <article class="card" style="margin-bottom:1rem;">
        <div class="card-kicker">${escapeHtml(ed.date)} &bull; ${escapeHtml(ed.edition_type.toUpperCase())}</div>
        <h3><a href="${escapeHtml(ed.url)}">${escapeHtml(ed.headline)}</a></h3>
        <a href="${escapeHtml(ed.url)}">Open Edition &rarr;</a>
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
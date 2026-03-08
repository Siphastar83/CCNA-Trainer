/* ══════════════════════════════════════════════════════════
   CCNA Quiz — script.js
══════════════════════════════════════════════════════════ */

// ── Fichiers JSON à charger ────────────────────────────────────────────────────
// ALL_FILES   : questions utilisées pour Libre / Tout réviser / Relier
// EXAM_FILE   : questions utilisées exclusivement pour le Mode Examen
const JSON_DIR = "scraped_questions/";
const EXAM_FILE = JSON_DIR + "ccna_questions_part8.json";
const ALL_FILES = [
    JSON_DIR + "ccna_questions_part1.json",
    JSON_DIR + "ccna_questions_part2.json",
    JSON_DIR + "ccna_questions_part3.json",
    JSON_DIR + "ccna_questions_part4.json",
    JSON_DIR + "ccna_questions_part5.json",
    JSON_DIR + "ccna_questions_part6.json",
    JSON_DIR + "ccna_questions_part7.json",
    JSON_DIR + "ccna_questions_part8.json",
];

// ── LocalStorage — questions signalées ─────────────────────────────────────────
const STORAGE_KEY = "ccna_reported_v1";

function loadReported() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (e) {
        return {};
    }
}
function saveReported(data) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {}
}

let REPORTED = loadReported();

function qHash(q) {
    return (q.question || "").slice(0, 80).replace(/\s+/g, " ").trim();
}
function isReported(q) {
    return !!REPORTED[qHash(q)];
}
function reportQuestion(q, reason, note) {
    REPORTED[qHash(q)] = { reason, note, date: new Date().toLocaleDateString("fr-FR"), question_snapshot: q };
    saveReported(REPORTED);
    updateMenuStats();
}
function unreportQuestion(hash) {
    delete REPORTED[hash];
    saveReported(REPORTED);
    updateMenuStats();
}
function unreportAll() {
    REPORTED = {};
    saveReported(REPORTED);
    updateMenuStats();
}

// ── State ──────────────────────────────────────────────────────────────────────
let ALL_Q = []; // toutes les questions (part1..part8, dédoublonnées)
let EXAM_Q = []; // questions du mode examen (part8 uniquement)

let SESSION = [];
let idx = 0,
    score = 0,
    wrongQ = [];
let answered = false;

// MCQ
let shuffledAnswers = [],
    selectedAnswers = new Set();
// Matching
let matchTerms = [],
    matchDefs = [],
    matchSelectedTerm = null;
let matchUserPairs = {},
    matchCorrectMap = {};
// Free mode
let freeTypeFilter = "all";
// Report
let selectedReason = null;

// ══════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════
async function fetchJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${url}`);
    return r.json();
}

function normalize(questions) {
    return questions.map((q) => ({ type: "multiple_choice", ...q }));
}

function dedup(questions) {
    const seen = new Set();
    return questions.filter((q) => {
        const h = qHash(q);
        if (seen.has(h)) return false;
        seen.add(h);
        return true;
    });
}

async function loadQuestions() {
    // Charge tous les fichiers en parallèle, ignore les manquants
    const results = await Promise.allSettled(ALL_FILES.map(fetchJSON));
    const merged = [];
    results.forEach((r, i) => {
        if (r.status === "fulfilled") merged.push(...r.value);
        else console.warn(`⚠ Impossible de charger ${ALL_FILES[i]}`);
    });

    ALL_Q = normalize(dedup(merged));

    // Charge le fichier examen séparément
    try {
        const examRaw = await fetchJSON(EXAM_FILE);
        EXAM_Q = normalize(examRaw);
    } catch (e) {
        console.warn("⚠ Fichier examen introuvable, fallback sur ALL_Q");
        EXAM_Q = ALL_Q;
    }

    if (ALL_Q.length === 0) {
        // Fallback démo si aucun fichier JSON n'est disponible (dev local sans serveur)
        ALL_Q = normalize(DEMO_QUESTIONS);
        EXAM_Q = normalize(DEMO_QUESTIONS);
    }

    updateMenuStats();
}

function availableQuestions(pool) {
    return (pool || ALL_Q).filter((q) => !isReported(q));
}

function updateMenuStats() {
    const avail = availableQuestions();
    const examAvail = availableQuestions(EXAM_Q);
    const qcm = avail.filter((q) => q.type === "multiple_choice").length;
    const mat = avail.filter((q) => q.type === "matching").length;
    const nRep = Object.keys(REPORTED).length;

    document.getElementById("stat-total").textContent = avail.length;
    document.getElementById("stat-qcm").textContent = qcm;
    document.getElementById("stat-match").textContent = mat;
    document.getElementById("stat-exam").textContent = examAvail.length;
    document.getElementById("stat-reported").textContent = nRep;
    document.getElementById("stat-reported-wrap").classList.toggle("hidden", nRep === 0);
}

// ══════════════════════════════════════════════════════════
// VIEWS
// ══════════════════════════════════════════════════════════
function showView(id) {
    ["menu", "quiz", "results", "reported-panel"].forEach((v) => {
        document.getElementById(v).classList.toggle("hidden", v !== id);
    });
    window.scrollTo(0, 0);
}
function goMenu() {
    showView("menu");
    updateMenuStats();
}

// ══════════════════════════════════════════════════════════
// SHUFFLE
// ══════════════════════════════════════════════════════════
function shuffle(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
}

// ══════════════════════════════════════════════════════════
// MODE LAUNCHERS
// ══════════════════════════════════════════════════════════
function startExam() {
    // Mode Examen → uniquement part8, max 60 questions
    const pool = availableQuestions(EXAM_Q);
    if (!pool.length) {
        alert("Aucune question disponible pour le mode examen.");
        return;
    }
    startSession(shuffle(pool).slice(0, Math.min(60, pool.length)));
}

function startMatchOnly() {
    const pool = availableQuestions().filter((q) => q.type === "matching");
    if (!pool.length) {
        alert("Aucune question à relier disponible.");
        return;
    }
    startSession(shuffle(pool));
}

function startAll() {
    startSession(shuffle(availableQuestions()));
}

function openFreeDialog() {
    updateFreeLabel();
    document.getElementById("free-dialog").classList.remove("hidden");
}
function closeFreeDialog() {
    document.getElementById("free-dialog").classList.add("hidden");
}

function selectType(el) {
    document.querySelectorAll(".filter-tab").forEach((t) => t.classList.remove("active"));
    el.classList.add("active");
    freeTypeFilter = el.dataset.type;
    updateFreeLabel();
}

function updateFreeLabel() {
    const pool = freeTypeFilter === "all" ? availableQuestions() : availableQuestions().filter((q) => q.type === freeTypeFilter);
    document.getElementById("free-max-label").textContent = `Nombre de questions (1 – ${pool.length})`;
    const inp = document.getElementById("free-n");
    inp.max = pool.length;
    if (parseInt(inp.value) > pool.length) inp.value = pool.length;
}

function startFree() {
    const pool = freeTypeFilter === "all" ? availableQuestions() : availableQuestions().filter((q) => q.type === freeTypeFilter);
    const n = Math.min(Math.max(1, parseInt(document.getElementById("free-n").value) || 20), pool.length);
    closeFreeDialog();
    startSession(shuffle(pool).slice(0, n));
}

function startSession(questions) {
    if (!questions.length) {
        alert("Aucune question disponible.");
        return;
    }
    SESSION = questions;
    idx = 0;
    score = 0;
    wrongQ = [];
    showView("quiz");
    renderQuestion();
}

function replaySession() {
    startSession(shuffle(SESSION));
}
function retryWrong() {
    if (wrongQ.length) startSession(shuffle(wrongQ));
}

// ══════════════════════════════════════════════════════════
// REPORT SYSTEM
// ══════════════════════════════════════════════════════════
const REASON_LABELS = {
    wrong_answer: "❌ Réponse incorrecte",
    wrong_question: "❓ Question mal formulée",
    display_bug: "🖥 Problème d'affichage",
    duplicate: "📋 Question en double",
};

function openReportDialog() {
    if (isReported(SESSION[idx])) return;
    selectedReason = null;
    document.querySelectorAll(".report-choice").forEach((c) => c.classList.remove("selected"));
    document.getElementById("report-note").value = "";
    document.getElementById("report-dialog").classList.remove("hidden");
}
function closeReportDialog() {
    document.getElementById("report-dialog").classList.add("hidden");
}
function selectReason(el) {
    document.querySelectorAll(".report-choice").forEach((c) => c.classList.remove("selected"));
    el.classList.add("selected");
    selectedReason = el.dataset.reason;
}
function submitReport() {
    if (!selectedReason) {
        alert("Sélectionnez un type d'erreur.");
        return;
    }
    const note = document.getElementById("report-note").value.trim();
    reportQuestion(SESSION[idx], selectedReason, note);
    closeReportDialog();
    const btn = document.getElementById("report-btn");
    btn.textContent = "⚑ Signalée";
    btn.classList.add("reported");
    btn.disabled = true;
    setFeedback("⚑ Question signalée et masquée pour les prochaines sessions.", "warn");
}

function showReportBtn() {
    const q = SESSION[idx];
    const btn = document.getElementById("report-btn");
    btn.classList.add("visible");
    if (isReported(q)) {
        btn.textContent = "⚑ Signalée";
        btn.classList.add("reported");
        btn.disabled = true;
    } else {
        btn.textContent = "⚑ Signaler";
        btn.classList.remove("reported");
        btn.disabled = false;
    }
}
function hideReportBtn() {
    const btn = document.getElementById("report-btn");
    btn.classList.remove("visible", "reported");
    btn.disabled = false;
}

// ── Reported panel ─────────────────────────────────────────────────────────────
function showReportedPanel() {
    showView("reported-panel");
    renderReportedPanel();
}

function renderReportedPanel() {
    const body = document.getElementById("panel-body");
    const items = Object.entries(REPORTED);

    if (!items.length) {
        body.innerHTML = `<div class="empty-panel">
      <div class="ep-icon">✅</div>
      <p>Aucune question signalée.<br>Toutes les questions sont actives.</p>
    </div>`;
        return;
    }

    let html = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
    <span style="font-size:13px;color:var(--dim)">${items.length} question${items.length > 1 ? "s" : ""} masquée${items.length > 1 ? "s" : ""}</span>
    <button class="btn btn-dim btn-sm" onclick="confirmUnreportAll()">Tout débloquer</button>
  </div>`;

    items.forEach(([hash, report]) => {
        const q = report.question_snapshot;
        const lab = REASON_LABELS[report.reason] || report.reason;

        let answersHtml = "";
        if (q.type === "matching") {
            (q.pairs || []).forEach((p) => {
                answersHtml += `<div class="ri-ans pairs-row">✔ ${escHtml(p.term)} → ${escHtml(p.definition)}</div>`;
            });
        } else {
            (q.answers || []).forEach((a) => {
                answersHtml += `<div class="ri-ans ${a.correct ? "correct" : ""}">${a.correct ? "✔" : " "} ${escHtml(a.answer)}</div>`;
            });
        }

        html += `<div class="reported-item">
      <div class="reported-item-head" onclick="toggleReportedItem(this)">
        <div class="ri-flag">⚑</div>
        <div class="ri-info">
          <div class="ri-reason">${lab}</div>
          <div class="ri-q">${escHtml(q.question)}</div>
          ${report.note ? `<div class="ri-note">"${escHtml(report.note)}"</div>` : ""}
        </div>
        <div class="ri-date">${report.date}</div>
      </div>
      <div class="reported-item-body hidden">
        <div class="ri-full-q">${escHtml(q.question)}</div>
        <div class="ri-answers">${answersHtml}</div>
        <div class="ri-body-btns">
          <button class="btn btn-primary btn-sm" onclick="unreportAndRefresh('${escAttr(hash)}')">✔ Débloquer</button>
          <button class="btn btn-dim btn-sm" onclick="toggleReportedItem(this.closest('.reported-item').querySelector('.reported-item-head'))">Fermer</button>
        </div>
      </div>
    </div>`;
    });

    body.innerHTML = html;
}

function toggleReportedItem(head) {
    head.nextElementSibling.classList.toggle("hidden");
}
function unreportAndRefresh(hash) {
    unreportQuestion(hash);
    renderReportedPanel();
}
function confirmUnreportAll() {
    if (confirm(`Débloquer les ${Object.keys(REPORTED).length} questions signalées ?`)) {
        unreportAll();
        renderReportedPanel();
    }
}

// ══════════════════════════════════════════════════════════
// RENDER QUESTION
// ══════════════════════════════════════════════════════════
function renderQuestion() {
    answered = false;
    selectedAnswers = new Set();
    matchSelectedTerm = null;
    matchUserPairs = {};
    hideReportBtn();

    const q = SESSION[idx];
    const total = SESSION.length;
    const num = idx + 1;

    document.getElementById("q-counter").textContent = `Q ${num}/${total}  ·  ✔${score} ✘${num - 1 - score}`;
    document.getElementById("progress-fill").style.width = `${((num - 1) / total) * 100}%`;

    const tag = document.getElementById("q-tag");
    if (q.type === "matching") {
        tag.textContent = "🔗 Relier";
        tag.style.borderColor = "var(--purple)";
        tag.style.color = "var(--purple)";
    } else {
        const multi = (q.answers || []).filter((a) => a.correct).length > 1;
        tag.textContent = multi ? "✦ Plusieurs réponses" : "● 1 réponse";
        tag.style.borderColor = multi ? "var(--yellow)" : "var(--blue)";
        tag.style.color = multi ? "var(--yellow)" : "var(--blue)";
    }

    document.getElementById("validate-btn").textContent = "Valider →";
    setFeedback("", "");

    const body = document.getElementById("quiz-body");
    q.type === "matching" ? renderMatching(q, body) : renderMCQ(q, body);
}

// ── MCQ ──────────────────────────────────────────────────────────────────────
function renderMCQ(q, body) {
    const multi = (q.answers || []).filter((a) => a.correct).length > 1;
    shuffledAnswers = shuffle(q.answers || []);
    const labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

    let html = `<div class="q-card">
    <div class="q-label">QUESTION</div>`;
    if (q.image_url) {
        html += `<img class="q-image" src="${q.image_url}" alt="schéma" loading="lazy" onerror="this.style.display='none'">`;
    }
    html += `<div class="q-text">${escHtml(q.question)}</div></div>
  <div class="answers">`;
    shuffledAnswers.forEach((a, i) => {
        html += `<div class="answer-row" id="ans-${i}" onclick="toggleAnswer(${i})">
      <div class="answer-badge" id="badge-${i}">${labels[i]}</div>
      <div class="answer-text">${escHtml(a.answer)}</div>
      <div class="answer-icon" id="icon-${i}">${multi ? "☐" : "○"}</div>
    </div>`;
    });
    html += "</div>";
    body.innerHTML = html;
}

function toggleAnswer(i) {
    if (answered) return;
    const multi = (SESSION[idx].answers || []).filter((a) => a.correct).length > 1;
    if (!multi) {
        selectedAnswers.forEach((j) => {
            document.getElementById(`ans-${j}`).classList.remove("selected");
            document.getElementById(`icon-${j}`).textContent = "○";
        });
        selectedAnswers.clear();
    }
    if (selectedAnswers.has(i)) {
        selectedAnswers.delete(i);
        document.getElementById(`ans-${i}`).classList.remove("selected");
        document.getElementById(`icon-${i}`).textContent = multi ? "☐" : "○";
    } else {
        selectedAnswers.add(i);
        document.getElementById(`ans-${i}`).classList.add("selected");
        document.getElementById(`icon-${i}`).textContent = multi ? "✔" : "●";
    }
}

function validateMCQ() {
    const q = SESSION[idx];
    const correctSet = new Set(shuffledAnswers.map((a, i) => (a.correct ? i : -1)).filter((i) => i >= 0));
    if (!selectedAnswers.size) {
        setFeedback("⚠ Sélectionnez au moins une réponse.", "warn");
        return;
    }

    answered = true;
    const ok = selectedAnswers.size === correctSet.size && [...selectedAnswers].every((i) => correctSet.has(i));

    if (ok) {
        score++;
        setFeedback("✔ Correct !", "ok");
    } else {
        wrongQ.push(q);
        setFeedback("✘ Incorrect", "bad");
    }

    shuffledAnswers.forEach((a, i) => {
        const row = document.getElementById(`ans-${i}`);
        const icon = document.getElementById(`icon-${i}`);
        row.classList.add("locked");
        if (correctSet.has(i)) {
            row.classList.remove("selected");
            row.classList.add("correct");
            icon.textContent = "✔";
        } else if (selectedAnswers.has(i)) {
            row.classList.remove("selected");
            row.classList.add("wrong");
            icon.textContent = "✘";
        }
    });

    showReportBtn();
    updateValidateBtn();
}

// ── Matching ──────────────────────────────────────────────────────────────────
function renderMatching(q, body) {
    const pairs = q.pairs || [];
    matchTerms = pairs.map((p) => p.term);
    matchDefs = shuffle(pairs.map((p) => p.definition));
    matchCorrectMap = {};
    matchTerms.forEach((term, ti) => {
        const cd = pairs.find((p) => p.term === term).definition;
        matchCorrectMap[ti] = matchDefs.indexOf(cd);
    });

    let html = `<div class="q-card">
    <div class="q-label matching">QUESTION À RELIER</div>`;
    if (q.image_url) {
        html += `<img class="q-image" src="${q.image_url}" alt="schéma" loading="lazy" onerror="this.style.display='none'">`;
    }
    html += `<div class="q-text">${escHtml(q.question)}</div></div>
  <div class="matching-hint">① Cliquez un <b style="color:var(--purple)">terme</b> → ② puis une <b style="color:var(--blue)">définition</b></div>
  <div class="matching-grid">
    <div class="matching-col"><div class="matching-col-label">TERMES</div>`;
    matchTerms.forEach((t, i) => {
        html += `<button class="match-btn" id="term-${i}" onclick="matchPickTerm(${i})">${escHtml(t)}</button>`;
    });
    html += `</div><div class="matching-col"><div class="matching-col-label">DÉFINITIONS</div>`;
    matchDefs.forEach((d, i) => {
        html += `<button class="match-btn" id="def-${i}" onclick="matchPickDef(${i})">${escHtml(d)}</button>`;
    });
    html += "</div></div>";
    body.innerHTML = html;
}

function matchPickTerm(ti) {
    if (answered) return;
    matchTerms.forEach((_, i) => {
        document.getElementById(`term-${i}`).classList.remove("term-selected");
        if (matchUserPairs[i] !== undefined) document.getElementById(`term-${i}`).classList.add("paired");
    });
    matchSelectedTerm = ti;
    document.getElementById(`term-${ti}`).classList.add("term-selected");
}

function matchPickDef(di) {
    if (answered) return;
    if (matchSelectedTerm === null) {
        setFeedback("⚠ Cliquez d'abord un terme.", "warn");
        return;
    }
    const ti = matchSelectedTerm;
    Object.keys(matchUserPairs).forEach((k) => {
        const kn = parseInt(k);
        if (kn === ti || matchUserPairs[kn] === di) {
            const old = matchUserPairs[kn];
            delete matchUserPairs[kn];
            document.getElementById(`term-${kn}`).classList.remove("paired", "term-selected");
            document.getElementById(`def-${old}`).classList.remove("paired");
        }
    });
    matchUserPairs[ti] = di;
    document.getElementById(`term-${ti}`).classList.remove("term-selected");
    document.getElementById(`term-${ti}`).classList.add("paired");
    document.getElementById(`def-${di}`).classList.add("paired");
    matchSelectedTerm = null;
    const n = Object.keys(matchUserPairs).length,
        tot = matchTerms.length;
    setFeedback(`${n}/${tot} paires reliées${n === tot ? " — Prêt !" : ""}`, n === tot ? "ok" : "");
}

function validateMatching() {
    const n = Object.keys(matchUserPairs).length;
    if (n < matchTerms.length) {
        setFeedback(`⚠ Reliez toutes les paires (${n}/${matchTerms.length})`, "warn");
        return;
    }
    answered = true;
    let nbOk = 0;
    Object.entries(matchUserPairs).forEach(([ti, di]) => {
        const ok = parseInt(di) === matchCorrectMap[parseInt(ti)];
        if (ok) nbOk++;
        document.getElementById(`term-${ti}`).classList.add(ok ? "match-correct" : "match-wrong", "locked");
        document.getElementById(`def-${di}`).classList.add(ok ? "match-correct" : "match-wrong", "locked");
    });
    Object.keys(matchCorrectMap).forEach((ti) => {
        const cd = matchCorrectMap[parseInt(ti)];
        if (matchUserPairs[parseInt(ti)] !== cd) document.getElementById(`def-${cd}`).classList.add("match-correct-hint", "locked");
    });
    document.querySelectorAll(".match-btn").forEach((b) => b.classList.add("locked"));
    const perfect = nbOk === matchTerms.length;
    if (perfect) {
        score++;
        setFeedback("✔ Parfait ! Toutes les paires sont correctes.", "ok");
    } else {
        wrongQ.push(SESSION[idx]);
        setFeedback(`✘ ${nbOk}/${matchTerms.length} paires correctes`, "bad");
    }
    showReportBtn();
    updateValidateBtn();
}

// ── Validate dispatcher ────────────────────────────────────────────────────────
function handleValidate() {
    if (answered) {
        nextQuestion();
        return;
    }
    SESSION[idx].type === "matching" ? validateMatching() : validateMCQ();
}

function nextQuestion() {
    idx++;
    if (idx >= SESSION.length) showResults();
    else renderQuestion();
}

function updateValidateBtn() {
    document.getElementById("validate-btn").textContent = idx === SESSION.length - 1 ? "Résultats →" : "Suivant →";
}

// ── Results ────────────────────────────────────────────────────────────────────
function showResults() {
    showView("results");
    const total = SESSION.length,
        pct = Math.round((score / total) * 100);
    let color, grade;
    if (pct >= 70) {
        color = "var(--right)";
        grade = "RÉUSSI ✔";
    } else if (pct >= 50) {
        color = "var(--yellow)";
        grade = "MOYEN ⚡";
    } else {
        color = "var(--wrong)";
        grade = "ÉCHOUÉ ✘";
    }

    document.getElementById("score-big").textContent = score;
    document.getElementById("score-big").style.color = color;
    document.getElementById("score-sub").textContent = `sur ${total} questions · ${pct}%`;
    document.getElementById("results-grade").textContent = grade;
    document.getElementById("results-grade").style.color = color;
    document.getElementById("pbar-fill").style.background = color;
    setTimeout(() => {
        document.getElementById("pbar-fill").style.width = pct + "%";
    }, 100);
    document.getElementById("retry-wrong-btn").style.display = wrongQ.length ? "" : "none";

    const list = document.getElementById("wrong-list");
    if (!wrongQ.length) {
        list.innerHTML = "";
        return;
    }
    let html = `<h3>✘ Questions ratées (${wrongQ.length})</h3>`;
    wrongQ.forEach((q) => {
        html += `<div class="wrong-item"><div class="wrong-q">${escHtml(q.question)}</div><div class="wrong-ans">`;
        if (q.type === "matching")
            (q.pairs || []).forEach((p) => {
                html += `✔ ${escHtml(p.term)} → ${escHtml(p.definition)}<br>`;
            });
        else
            (q.answers || [])
                .filter((a) => a.correct)
                .forEach((a) => {
                    html += `✔ ${escHtml(a.answer)}<br>`;
                });
        html += "</div></div>";
    });
    list.innerHTML = html;
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function setFeedback(msg, type) {
    const el = document.getElementById("feedback");
    el.textContent = msg;
    el.className = "feedback" + (type ? " " + type : "");
}
function escHtml(s) {
    return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
function escAttr(s) {
    return String(s || "")
        .replace(/'/g, "&#39;")
        .replace(/"/g, "&quot;");
}

// ══════════════════════════════════════════════════════════
// DEMO DATA — fallback si les fichiers JSON sont absents
// ══════════════════════════════════════════════════════════
const DEMO_QUESTIONS = [
    {
        question:
            "Un administrateur a défini un compte d'utilisateur local avec un mot de passe secret sur le routeur R1. Quelles sont les trois étapes supplémentaires nécessaires pour configurer R1 pour accepter uniquement les connexions SSH chiffrées ? (Choisissez trois réponses.)",
        type: "multiple_choice",
        answers: [
            { answer: "Activez les sessions SSH entrantes à l'aide des commandes de ligne VTY.", correct: true },
            { answer: "Configurer le nom de domaine IP.", correct: true },
            { answer: "Générez des clés pré-partagées bidirectionnelles.", correct: false },
            { answer: "Configurez DNS sur le routeur.", correct: false },
            { answer: "Activez les sessions Telnet entrantes.", correct: false },
            { answer: "Générer les clés SSH.", correct: true },
        ],
    },
    {
        question: "Que sont les protocoles propriétaires ?",
        type: "multiple_choice",
        answers: [
            { answer: "Des protocoles librement utilisés par toute entreprise", correct: false },
            { answer: "Un ensemble de protocoles connus sous le nom de suite TCP/IP", correct: false },
            { answer: "Des protocoles développés par des entreprises qui contrôlent leur définition", correct: true },
            { answer: "Des protocoles développés par des organismes privés pour tout fournisseur", correct: false },
        ],
    },
    {
        question: "Reliez chaque description au terme correspondant.",
        type: "matching",
        pairs: [
            { term: "Dimensionnement des messages", definition: "Processus consistant à décomposer un message long en parties distinctes avant de les envoyer" },
            { term: "Encapsulation des messages", definition: "Processus consistant à placer un format de message à l'intérieur d'un autre" },
            { term: "Codage des messages", definition: "Processus permettant de convertir des informations dans un format acceptable pour la transmission" },
        ],
    },
];

// ── Init ───────────────────────────────────────────────────────────────────────
loadQuestions();

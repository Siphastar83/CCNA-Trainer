import requests
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path

# ── URLs à scraper ─────────────────────────────────────────────────────────────
URLS = [
    "https://ccnareponses.com/modules-1-3-examen-sur-la-connectivite-des-reseaux-de-base-et-les-communications-reponses/",
    "https://ccnareponses.com/modules-4-7-examen-sur-les-concepts-dethernet-reponses/",
    "https://ccnareponses.com/modules-8-10-examen-sur-la-communication-entre-les-reseaux-reponses/",
    "https://ccnareponses.com/modules-11-13-examen-sur-ladressage-ip-reponses/",
    "https://ccnareponses.com/modules-14-15-examen-sur-les-communications-des-applications-du-reseau-reponses/",
    "https://ccnareponses.com/modules-16-17-examen-sur-la-creation-et-la-securisation-dun-reseau-de-petit-taille-reponses/",
    "https://ccnareponses.com/itnv7-practice-final-exam-examen-blanc-final-reponses-francais/",
    "https://ccnareponses.com/ccna-1-examen-final-itnv7-questions-et-reponses-francais/"
]

number_pattern  = re.compile(r"^\d+\.\s*")
# Préfixes d'explication à supprimer si jamais ils se glissent dans le texte
explain_pattern = re.compile(
    r"^(Explique?\s*:\s*|Explication\s*:\s*|Expliquer\s*:\s*)", re.IGNORECASE
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def is_correct_li(li):
    """Détecte si un <li> est une bonne réponse (class OU couleur rouge)."""
    if "correct_answer" in li.get("class", []):
        return True
    for child in li.find_all(True):
        style = child.get("style", "")
        if "ff0000" in style or "red" in style:
            return True
    return False


def is_message_box(tag):
    """Retourne True si le tag est un bloc d'explication (message_box)."""
    if not hasattr(tag, "get"):
        return False
    classes = " ".join(tag.get("class", []))
    return "message_box" in classes or "announce" in classes


def extract_question_text(tag):
    """
    Extrait UNIQUEMENT le texte de la question depuis un <p> ou <strong>.

    Stratégie :
    - Si le tag contient un <strong>, on prend le texte du/des <strong>
      (ce qui exclut les blocs message_box et autres divs parasites).
    - Sinon on prend le texte brut du tag.
    - On supprime ensuite le numéro de début et les préfixes "Explique:".
    """
    strong_tags = tag.find_all("strong") if hasattr(tag, "find_all") else []

    if strong_tags:
        # Concaténer le texte de tous les <strong> du tag
        text = " ".join(s.get_text(separator=" ", strip=True) for s in strong_tags)
    else:
        # Pas de <strong> : texte brut (cas du tag <strong> lui-même)
        text = tag.get_text(separator=" ", strip=True)

    # Nettoyer le numéro de question
    text = number_pattern.sub("", text).strip()

    # Supprimer les préfixes d'explication résiduels
    text = explain_pattern.sub("", text).strip()

    return text


def get_image_url(tag):
    """Cherche une image dans le tag ou ses siblings proches."""
    img = tag.find("img")
    if img:
        return img.get("src", "")
    # Chercher dans le sibling suivant
    nxt = tag.find_next_sibling()
    if nxt:
        img = nxt.find("img")
        if img:
            return img.get("src", "")
    return None


def extract_ul_answers(ul_tag):
    """Extrait les réponses d'un <ul>."""
    answers = []
    for li in ul_tag.find_all("li", recursive=False):
        answer_text = li.get_text(strip=True)
        if not answer_text:
            continue
        answers.append({
            "answer": answer_text,
            "correct": is_correct_li(li)
        })
    return answers


def extract_table_pairs(table_tag):
    """Extrait les paires (terme → définition) d'un <table>."""
    pairs = []
    for row in table_tag.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            term = cells[0].get_text(strip=True)
            definition = cells[1].get_text(strip=True)
            if term and definition:
                pairs.append({"term": term, "definition": definition})
    return pairs


def is_question_tag(tag):
    """
    Retourne True si ce tag contient probablement une question.
    On cherche un <strong> ou un texte dans <p> suivi d'un numéro.
    """
    if tag.name not in ("p", "strong"):
        return False
    text = tag.get_text(strip=True)
    if len(text) < 10:
        return False
    # Le texte doit contenir une marque de question ou un numéro
    has_number = bool(re.match(r"^\d+\.", text))
    has_strong = bool(tag.find("strong"))
    has_question_mark = "?" in text
    return has_number or has_strong or has_question_mark


# ── Scraper principal ──────────────────────────────────────────────────────────

def scrap_page(url):
    print(f"Scraping {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    content_div = soup.find("div", class_="post-content cf entry-content content-spacious")
    if not content_div:
        print("  ⚠ Conteneur principal non trouvé !")
        return []

    questions_data = []
    seen_questions = set()  # éviter les doublons

    # On itère sur tous les tags enfants directs du contenu
    children = list(content_div.children)

    i = 0
    while i < len(children):
        tag = children[i]

        # Ignorer les navigables string (texte brut, espaces)
        if not hasattr(tag, "name") or tag.name is None:
            i += 1
            continue

        # ── Ignorer les blocs d'explication (message_box / announce) ───────────
        if is_message_box(tag):
            i += 1
            continue
        # Ignorer aussi les <p> qui contiennent un message_box en enfant direct
        if tag.name == "p" and any(is_message_box(c) for c in tag.children
                                   if hasattr(c, "name")):
            i += 1
            continue

        # ── Cas 1 : <p> contenant un <strong> (question standard) ──────────────
        if tag.name == "p" and tag.find("strong"):
            question_text = extract_question_text(tag)
            if not question_text or len(question_text) < 8:
                i += 1
                continue
            if question_text in seen_questions:
                i += 1
                continue

            # Chercher l'image dans ce <p> ou le suivant
            image_url = get_image_url(tag)

            # Chercher le prochain sibling pertinent
            j = i + 1
            found = False
            while j < len(children) and j < i + 8:
                sibling = children[j]
                if not hasattr(sibling, "name") or sibling.name is None:
                    j += 1
                    continue

                # Sauter les blocs d'explication
                if is_message_box(sibling):
                    j += 1
                    continue

                # Questions à choix multiples → <ul>
                if sibling.name == "ul":
                    answers = extract_ul_answers(sibling)
                    if answers:
                        entry = {
                            "question": question_text,
                            "type": "multiple_choice",
                            "answers": answers
                        }
                        if image_url:
                            entry["image_url"] = image_url
                        questions_data.append(entry)
                        seen_questions.add(question_text)
                        found = True
                    break

                # Questions à relier → <table>
                if sibling.name == "table":
                    pairs = extract_table_pairs(sibling)
                    if pairs:
                        entry = {
                            "question": question_text,
                            "type": "matching",
                            "pairs": pairs
                        }
                        if image_url:
                            entry["image_url"] = image_url
                        questions_data.append(entry)
                        seen_questions.add(question_text)
                        found = True
                    break

                # Si on rencontre une nouvelle question, on arrête
                if sibling.name == "p" and sibling.find("strong"):
                    break
                if sibling.name in ("h2", "h3", "h4"):
                    break

                # Si on rencontre une image, on la mémorise pour la question
                if sibling.name == "p":
                    img = sibling.find("img")
                    if img and not image_url:
                        image_url = img.get("src", "")

                j += 1

            i += 1
            continue

        # ── Cas 2 : <strong> seul (question sans <p>) ──────────────────────────
        if tag.name == "strong":
            question_text = extract_question_text(tag)
            if not question_text or len(question_text) < 8:
                i += 1
                continue
            if question_text in seen_questions:
                i += 1
                continue

            image_url = None
            j = i + 1
            while j < len(children) and j < i + 8:
                sibling = children[j]
                if not hasattr(sibling, "name") or sibling.name is None:
                    j += 1
                    continue

                # Sauter les blocs d'explication
                if is_message_box(sibling):
                    j += 1
                    continue

                if sibling.name == "ul":
                    answers = extract_ul_answers(sibling)
                    if answers:
                        entry = {
                            "question": question_text,
                            "type": "multiple_choice",
                            "answers": answers
                        }
                        if image_url:
                            entry["image_url"] = image_url
                        questions_data.append(entry)
                        seen_questions.add(question_text)
                    break

                if sibling.name == "table":
                    pairs = extract_table_pairs(sibling)
                    if pairs:
                        entry = {
                            "question": question_text,
                            "type": "matching",
                            "pairs": pairs
                        }
                        questions_data.append(entry)
                        seen_questions.add(question_text)
                    break

                if sibling.name == "p":
                    img = sibling.find("img")
                    if img and not image_url:
                        image_url = img.get("src", "")

                if sibling.name in ("h2", "h3", "h4"):
                    break

                j += 1

            i += 1
            continue

        i += 1

    # ── Nettoyage : retirer les questions sans réponses ────────────────────────
    valid = []
    for q in questions_data:
        if q["type"] == "multiple_choice" and q.get("answers"):
            valid.append(q)
        elif q["type"] == "matching" and q.get("pairs"):
            valid.append(q)

    print(f"  ✔ {len(valid)} questions extraites ({sum(1 for q in valid if q['type']=='matching')} matching, {sum(1 for q in valid if q['type']=='multiple_choice')} QCM)")
    return valid


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def scrap():
    output_dir = Path("scraped_questions")
    output_dir.mkdir(exist_ok=True)

    all_questions = []

    for idx, url in enumerate(URLS, start=1):
        questions = scrap_page(url)
        if questions:
            filename = output_dir / f"ccna_questions_part{idx}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(questions, f, ensure_ascii=False, indent=4)
            all_questions.extend(questions)

    merged_path = output_dir / "ccna_questions_all.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=4)

    qcm_count     = sum(1 for q in all_questions if q["type"] == "multiple_choice")
    matching_count = sum(1 for q in all_questions if q["type"] == "matching")
    print(f"\n✔ Total : {len(all_questions)} questions")
    print(f"  → {qcm_count} QCM (choix multiples)")
    print(f"  → {matching_count} questions à relier")
    print(f"  → Fichier fusionné : {merged_path}")


if __name__ == "__main__":
    scrap()
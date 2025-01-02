# -----------------------------------------
# Projet : Europresse to IRaMuTeQ - Appli streamlit
# Auteur : Stéphane Meurisse
# Contact : stephane.meurisse@gmail.com
# Site Web : https://www.codeandcortex.fr
# LinkedIn : https://www.linkedin.com/in/st%C3%A9phane-meurisse-27339055/
# Date : 31 Décembre 2024
# Version : 3.1.2
# Licence : Ce programme est un logiciel libre : vous pouvez le redistribuer selon les termes de la Licence Publique Générale GNU v3
# -----------------------------------------

import os
import re
import html
import csv
from bs4 import BeautifulSoup
import streamlit as st
from io import StringIO, BytesIO
import zipfile
import streamlit.components.v1 as components
from datetime import datetime


# -----------------------------------------
# 1) DICTIONNAIRE POUR LES DATES
# -----------------------------------------

# 1) Dictionnaire
mois_fr_en = {
    'janvier': 'January', 'février': 'February', 'mars': 'March',
    'avril': 'April', 'mai': 'May', 'juin': 'June',
    'juillet': 'July', 'août': 'August', 'septembre': 'September',
    'octobre': 'October', 'novembre': 'November', 'décembre': 'December'
}

# 2) Fonction paser la date
def parser_date(raw_date_str):
    """
    Transforme "31 décembre 2024" ou "June 13, 2024" en un objet datetime.
    Remplace les mois français par anglais si nécessaire.
    """
    # Remplacement des mois français par anglais
    for fr, en in mois_fr_en.items():
        if fr in raw_date_str.lower():
            raw_date_str = re.sub(fr, en, raw_date_str, flags=re.IGNORECASE)
            break  # Arrêter après la première correspondance

    try:
        # Tenter de parser au format "13 June 2024"
        date_obj = datetime.strptime(raw_date_str, "%d %B %Y")
        return date_obj
    except ValueError:
        try:
            # Tenter de parser au format "June 13, 2024"
            date_obj = datetime.strptime(raw_date_str, "%B %d, %Y")
            return date_obj
        except ValueError:
            return None  # Si le parsing échoue


# Fonction pour nettoyer le nom du journal
def nettoyer_nom_journal(nom_journal):
    nom_journal_sans_numero = nom_journal.split(",")[0]
    nom_journal_sans_numero = re.sub(r"[ ']", "_", nom_journal_sans_numero)
    nom_journal_nettoye = f"*source_{nom_journal_sans_numero}"
    return nom_journal_nettoye

def extraire_texte_html(
        contenu_html,
        variable_suppl_texte,
        nom_journal_checked,
        date_annee_mois_jour_checked,
        date_annee_mois_checked,
        date_annee_checked,
        methode_extraction,
        supprimer_balises=False  # par défaut False because expérimental
    ):

    soup = BeautifulSoup(contenu_html, 'html.parser')
    articles = soup.find_all('article')
    texte_final = ""
    data_for_csv = []

    for article in articles:
        # --------------------------------------------------------------------
        # 2) RÉCUPÉRATION DES INFORMATIONS (Journal + Date) - PREMIÈRE PARTIE
        # --------------------------------------------------------------------
        # a) Nom du journal (brut) via la balise .rdp__DocPublicationName

        nom_journal = ""
        div_journal = article.find("div", class_="rdp__DocPublicationName")
        if div_journal:
            span_journal = div_journal.find("span", class_="DocPublicationName")
            if span_journal:
                # On récupère tous les morceaux de texte dans cette balise
                content_list = list(span_journal.stripped_strings)
                if content_list:
                    # Exemple : "La Croix, no. 43018"
                    nom_journal = content_list[0]


        # --------------------------------------------------------------------
        # b) Extraction du texte brut (avant suppression plus fine)
        # --------------------------------------------------------------------
        # Maintenant que la div du journal a été retirée,
        # on obtient le texte complet de l'article.
        texte_article = article.get_text(" ", strip=True)

        # --------------------------------------------------------------------
        # 3) RÉCUPÉRATION DU NOM DU JOURNAL (selon la méthode choisie) - SECONDE PARTIE
        # --------------------------------------------------------------------
        # On retrouve (ou pas) à nouveau la div_journal
        # (Si elle a déjà été decompose(), elle sera None)
        div_journal = article.find("div", class_="rdp__DocPublicationName")
        nom_journal = ""
        nom_journal_formate = ""

        # Choix de la méthode d'extraction (0 ou 1)
        if methode_extraction == 0:
            # Méthode 0 : extraction "simple"
            if div_journal:
                span_journal = div_journal.find("span", class_="DocPublicationName")
                if span_journal:
                    # Récupération directe du texte
                    nom_journal = span_journal.get_text(strip=True)
                    # Nettoyage / formatage (ex: "*source_La_Croix")
                    nom_journal_formate = nettoyer_nom_journal(nom_journal)

        elif methode_extraction == 1:
            # Méthode 1 : extraction "plus granulaire" (via content_list)
            if div_journal:
                span_journal = div_journal.find("span", class_="DocPublicationName")
                if span_journal:
                    content_list = list(span_journal.stripped_strings)
                    if content_list:
                        nom_journal = content_list[0]
                    else:
                        nom_journal = ""
                    nom_journal_formate = nettoyer_nom_journal(nom_journal)

        # Supprime la div du DOM (si elle existe toujours)
        if div_journal:
            div_journal.decompose()


        # b) Date (brut) via la balise .DocHeader
        date_texte = ""
        raw_date_str = ""
        span_date = article.find("span", class_="DocHeader")
        if span_date:
            date_texte = html.unescape(span_date.get_text())
            # On cherche une date dans le format "5 janvier 2024"
            # match = re.search(r'\d{1,2} \w+ \d{4}', date_texte)
            # version fr et en
            match = re.search(r'\d{1,2} \w+ \d{4}|\w+ \d{1,2}, \d{4}', date_texte)
            if match:
                raw_date_str = match.group()  # ex: "11 septembre 2024"
            span_date.decompose()

        # --------------------------------------------------------------------
        # 4) FORMATTER CES INFORMATIONS EN VERSION "ÉTOILÉE"
        # --------------------------------------------------------------------
        #    ex: "*source_La_Croix *date_2024-09-11" ...

        nom_journal_formate = ""
        if nom_journal:
            nom_journal_formate = nettoyer_nom_journal(nom_journal)

        # Gestion de la date en format "année-mois-jour", "année-mois", "année"
        date_formattee = am_formattee = annee_formattee = ""
        if raw_date_str:
            date_obj = parser_date(raw_date_str)  # <-- on appelle la fonction
            if date_obj:
                date_formattee = date_obj.strftime('*date_%Y-%m-%d')  # ex: *date_2023-12-05
                am_formattee = date_obj.strftime('*am_%Y-%m')  # ex: *am_2023-12
                annee_formattee = date_obj.strftime('*annee_%Y')  # ex: *annee_2023

        # --------------------------------------------------------------------
        # 5) TITRE : on le veut dans le corps final, donc on ne le supprime pas
        # --------------------------------------------------------------------
        titre_article = ""
        p_titre = article.find("p", class_="sm-margin-TopNews titreArticleVisu rdp__articletitle")
        if p_titre:
            titre_article = p_titre.get_text(strip=True)
            # On ne le decompose() pas, on le laisse dans le DOM pour le get_text() final
            # Mais on pourrait stocker son texte si on veut le retravailler.

        # --------------------------------------------------------------------
        # 6) NETTOYAGE DU DOM (aside, footer, etc.) AVANT LE GET_TEXT
        # --------------------------------------------------------------------

        if supprimer_balises:
            termes_a_supprimer = ["Edito", "AUTRE", "Opinions", "La chronique", "Le point de vue", "ANTICIPATION", "Tech",
                         "Une-ECO", "spécial ia france", "Le figaro santé", "Débats", "Portrait", "Enquête",
                         "Chronique Etranger", "repères", "Société", "La vie des entreprises", "Rencontre",
                         "L'HISTOIRE", "Éthique", "SANTÉ PUBLIQUE", "Idées/", "Billet", "Economie & Entreprise", "Cinéma",
                         "Question du jour", "Médecine", "Internet", "Reportage", "International", "ÉVÉNEMENT",
                         "Le Figaro et vous", "Religion", "Premiere Page", "_Faits divers", "40TOUTES", "RODEZ_CP",
                         "France", "Politique", "Sciences et Santé", "_Politique", "Le fait du jour", "Actualité ; Société",
                         "AFP", "CONTRE-POINT", "Une", "Économie", "u FRANCE", "Expresso ", "Images/", "Histoire littéraire",
                         "France", "Le Monde des Livres", "Opinions", "critiques", "Télévision", "Interieur FigaroPlus",
                         "Le Monde Science et médecine", "CANNEs/", "_Société", "_Le Fait du jour", "IDÉES"]  # Liste des termes spécifiques à supprimer
            for p_tag in article.find_all("p", class_="sm-margin-bottomNews"):
                texte_p = p_tag.get_text(strip=True)
                if any(terme.lower() in texte_p.lower() for terme in termes_a_supprimer):
                    p_tag.decompose()

            for div_tag in article.find_all("div"):
                texte_div = div_tag.get_text(strip=True)
                if any(terme.lower() == texte_div.lower() for terme in termes_a_supprimer):
                    div_tag.decompose()

        ######

        for element in article.find_all(["head", "aside", "footer", "img", "a"]):
            element.decompose()
        # eventuellement, d'autres classes à supprimer
        for element in article.find_all("div", class_=["apd-wrapper"]):
            element.decompose()
        for element in article.find_all("p", class_="sm-margin-bottomNews"):
            element.decompose()
        # DÉBUT du bloc pour supprimer les <i> et <em>
        for i_tag in article.find_all("i"):
            i_tag.unwrap()
        for em_tag in article.find_all("em"):
            em_tag.unwrap()

        # --------------------------------------------------------------------
        # 7) SUPPRIMER LE CONTENU APRES LA DATE DANS 'titreArticle'
        # --------------------------------------------------------------------
        if supprimer_balises:
            titre_article_div = article.find("div", class_="titreArticle")
            if titre_article_div:
                # Supprimer tous les <p> tags sauf celui avec la classe 'sm-margin-TopNews titreArticleVisu rdp__articletitle'
                for p_tag in titre_article_div.find_all("p"):
                    classes = p_tag.get("class", [])
                    if not all(classe in classes for classe in
                                ["sm-margin-TopNews", "titreArticleVisu", "rdp__articletitle"]):
                        p_tag.decompose()


        # --------------------------------------------------------------------
        # 7) EXTRAIRE LE TEXTE FINAL
        # --------------------------------------------------------------------
        texte_article = article.get_text("\n", strip=True)
        # Le "\n" dans get_text() permet d’éviter que tout soit sur une seule ligne.

        # --------------------------------------------------------------------
        # 8) SUPPRIMER LE JOURNAL + DATE BRUTS DU TEXTE, tout en gardant le titre
        #    (car le titre se trouve dans le DOM au même endroit)
        # --------------------------------------------------------------------
        if nom_journal:
            # On supprime la chaîne brute "La Croix, no. 43018" par exemple
            texte_article = re.sub(re.escape(nom_journal), '', texte_article)

        if raw_date_str:
            # On supprime "31 décembre 2024" (ou autre)
            texte_article = re.sub(re.escape(raw_date_str), '', texte_article)

        if date_texte:
            # Selon vos besoins, vous pouvez vouloir enlever aussi "France, mercredi 11 septembre 2024 134 mots, p. 11"
            # si c'est présent tel quel
            texte_article = re.sub(re.escape(date_texte), '', texte_article)

        # --------------------------------------------------------------------
        # 9) RETOUCHE FINALE : enlever les doublons de lignes vides,...
        # --------------------------------------------------------------------
        # Par exemple, si la première ligne s’est retrouvée vide après la suppression
        # On peut couper par lignes, nettoyer, recoller
        lignes = [l.strip() for l in texte_article.splitlines() if l.strip()]
        texte_article = "\n".join(lignes)

        # Transforme tous les sauts de ligne en un espace
        texte_article = texte_article.replace('\n', ' ')

        # Nettoyer les expressions de liens
        texte_article = re.sub(r'\(lien : https?://[^)]+\)', '', texte_article)
        # OU : texte_article = re.sub(r'https?://\S+', '', texte_article)  # si vous voulez tout virer

        # Traitement des lignes pour ajouter un point à la première ligne et supprimer l'espace en début
        lignes = texte_article.splitlines()
        if lignes and not lignes[0].endswith('.'):
            lignes[0] += '.'
        lignes = [ligne.strip() for ligne in lignes]
        texte_article = '\n'.join(lignes)

        # LIGNE À AJOUTER pour éviter le saut de ligne devant le «
        texte_article = re.sub(r'\n+(?=«)', ' ', texte_article)

        # --------------------------------------------------------------------
        # 10) CONSTRUIRE LA PREMIÈRE LIGNE (étoilée) + CORPS
        # --------------------------------------------------------------------
        #    (==> "**** *source_La_Croix *date_2024-09-11 *am_2024-09 *annee_2024 *variable_suppl...")
        info_debut = "****"
        if nom_journal_checked and nom_journal_formate:
            info_debut += f" {nom_journal_formate}"
        if date_annee_mois_jour_checked and date_formattee:
            info_debut += f" {date_formattee}"
        if date_annee_mois_checked and am_formattee:
            info_debut += f" {am_formattee}"
        if date_annee_checked and annee_formattee:
            info_debut += f" {annee_formattee}"
        if variable_suppl_texte:
            info_debut += f" *{variable_suppl_texte}"
        info_debut += "\n"  # Fin de la 1ère ligne

        # --------------------------------------------------------------------
        # 11) ON AJOUTE LE TEXTE DE L’ARTICLE APRÈS
        # --------------------------------------------------------------------
        texte_final_article = info_debut + texte_article + "\n\n"
        texte_final += texte_final_article

        # --------------------------------------------------------------------
        # 12) ENREGISTRER FICHIER CSV
        # --------------------------------------------------------------------
        data_for_csv.append({
            'Journal': nom_journal_formate,
            'Année-mois-jour': date_formattee,
            'Année-mois': am_formattee,
            'Année': annee_formattee,
            'Article': texte_article
        })

    return texte_final, data_for_csv


# --------------------------------------------------------------------
#   INTERFACE GRAPHIQUE STREAMLIT
# --------------------------------------------------------------------

# Interface Streamlit
def afficher_interface_europresse():

    # Grand titre
    st.markdown(
        "<h1 style='text-align: center; font-size: 44px; margin-bottom: 0px; color: #FF5733;'>Europresse to IRaMuTeQ</h1>",
        unsafe_allow_html=True
    )

    # Sous-titre en plus petit (h3)
    st.markdown(
        "<h3 style='text-align: center; font-size: 34'px;'>Traitement des fichiers Europresse 😊</h3>",
        unsafe_allow_html=True
    )

    # Ligne de séparation
    st.markdown("---")
    st.markdown("""
        Cette application (no code !) vous permet de convertir facilement des fichiers HTML issus du site Europresse en 
        fichiers texte (.txt et .csv), prêts à être analysés avec le logiciel IRAMUTEQ.
        Le script (version 3.0) effectue un nettoyage du corpus et formate la première ligne de chaque article selon les exigences du
        logiciel.

        **** *source_nomdujournal *date_2023-12-22 *am_2023-12 *annee_2023
         """)

    # Lien vers votre site (en petit)
    st.markdown(
        """
        <p style="font-size:14px;">
            Consultez mon site où je partage des contenus autour de l'analyse de texte, de la data science et du NLP. 
            Si vous avez des questions, des retours ou des suggestions, n'hésitez pas à me contacter. 
            <a href="https://www.codeandcortex.fr" target="_blank">codeandxortex.fr</a>
        </p>
        """,
        unsafe_allow_html=True
    )

    # Ligne de séparation
    st.markdown("---")

    uploaded_file = st.file_uploader("Téléversez un fichier HTML Europresse", type="html")

    if uploaded_file:
        # variable_suppl_texte = st.text_input("Votre variable supplémentaire (optionnel)")
        nom_journal_checked = st.checkbox("Inclure le nom du journal", value=True)
        date_annee_mois_jour_checked = st.checkbox("Inclure la date (année-mois-jour)", value=True)
        date_annee_mois_checked = st.checkbox("Inclure la date (année-mois)", value=True)
        date_annee_checked = st.checkbox("Inclure l'année uniquement", value=True)
        variable_suppl_texte = st.text_input("Votre variable supplémentaire (optionnel)")

        # --- Explication des méthodes d'extraction (Markdown)
        st.markdown("""
            ### Explication des méthodes d'extraction :
            - **Méthode normale** : Extraction du nom du journal depuis la balise `div` sans aucun traitement - (On touche à rien et on exporte ! ).
            - **Méthode clean (conseillée)** : Extraction du nom du journal avec un traitement permettant de raccourcir le nom du journal.
            """)

        methode_extraction = st.radio(
            "Méthode d'extraction du nom du journal",
            (0, 1),
            format_func=lambda x: "Méthode normale" if x == 0 else "Méthode clean"
        )

        # **NOUVEAU** : bouton radio pour supprimer (ou non) les balises <p> contenant "Edito", "Autre", ...
        supprimer_balises_radio = st.radio(
            "Supprimer les balises contenant 'Edito', 'AUTRE',...(Expérimental ! à vos risques et périls !!!)",
            ("Non", "Oui"),
            index=0
        )

        if st.button("Lancer le traitement"):
            # 1) Récupérer le nom de fichier sans extension
            original_filename = uploaded_file.name  # ex: "mon_fichier.html"
            base_name, _ = os.path.splitext(original_filename)  # ("mon_fichier", ".html")

            # 2) Extraire le contenu HTML et traiter
            contenu_html = uploaded_file.getvalue().decode("utf-8")
            texte_final, data_for_csv = extraire_texte_html(
                contenu_html,
                variable_suppl_texte,
                nom_journal_checked,
                date_annee_mois_jour_checked,
                date_annee_mois_checked,
                date_annee_checked,
                methode_extraction,
                supprimer_balises = (supprimer_balises_radio == "Oui")
            )

            # 3) Créer un fichier CSV en mémoire
            csv_buffer = StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=['Journal', 'Date','Année-mois-jour','Année-mois','Année', 'Article'])
            writer.writeheader()
            for row in data_for_csv:
                writer.writerow(row)

            # 4) Construire un ZIP contenant le .txt et le .csv
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # Nommer les fichiers .txt et .csv comme le fichier HTML initial
                zf.writestr(f"{base_name}.txt", texte_final)
                zf.writestr(f"{base_name}.csv", csv_buffer.getvalue())

            # 5) Afficher un aperçu du texte final
            st.markdown("### Aperçu du corpus traité")
            st.text_area(
                label="",
                value=texte_final,
                height=300
            )

            # 6) Proposer le téléchargement du ZIP
            st.download_button(
                "Télécharger les fichiers (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f"{base_name}_outputs.zip",
                mime="application/zip"
            )

# Injection du script GA après le contenu
    GA_CODE = """
        <div style="display: none;">
            <!-- Google Analytics -->
            <script async src="https://www.googletagmanager.com/gtag/js?id=G-438652717"></script>
            <script>
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', 'G-438652717');
            </script>
        </div>
    """
    st.markdown(GA_CODE, unsafe_allow_html=True)

if __name__ == "__main__":
    afficher_interface_europresse()



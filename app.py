from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import streamlit as st
import pandas as pd
from pathlib import Path
from io import BytesIO
from xhtml2pdf import pisa
BASE_CSV = "https://docs.google.com/spreadsheets/d/17v8riPgTlZuHtLG7tetQMca0u_6emsfx/export?format=csv&gid=839414220"
MULT_CSV = "https://docs.google.com/spreadsheets/d/17v8riPgTlZuHtLG7tetQMca0u_6emsfx/export?format=csv&gid=2005657488"

# Then call:
cities_data, multipliers = load_parameters(BASE_CSV, MULT_CSV)

# Configure page FIRST - must be first Streamlit command
st.set_page_config(
    page_title="Simulateur de Tarification - Weego",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 1.2rem !important;
    }
    .stSuccess {
        background-color: #f0f9ff !important;
        border-color: #0068c9 !important;
    }
    .stAlert {
        padding: 1rem !important;
    }
    .highlight {
        background: linear-gradient(90deg, #fffd8c, #ffffff);
        padding: 0.5rem;
        border-radius: 0.5rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Title and subtitle
st.title("🚌 Simulateur de Tarification - Weego")
st.caption("Estimez rapidement les prix de transport selon la ville, la distance, et les conditions de service.")

# --- PARAMETERS LOADING ---
@st.cache_data
def load_parameters(gsheet_base_csv=None, gsheet_mult_csv=None):
    """
    Loads pricing parameters from either:
      1) Google Sheets CSV export URLs (recommended for online deployment), or
      2) local 'pricing_parameters.xlsx' for local usage.
    """
    # Try Google Sheets CSV first (if provided)
    try:
        if gsheet_base_csv and gsheet_mult_csv:
            df_rates = pd.read_csv(gsheet_base_csv)
            df_multipliers = pd.read_csv(gsheet_mult_csv)
        else:
            # fallback to local Excel
            base_path = Path(__file__).parent
            file_path = (base_path / "pricing_parameters.xlsx").resolve()
            if not file_path.exists():
                st.warning("Aucun fichier local trouvé et aucun Google Sheet fourni.")
                return {}, {}
            xls = pd.ExcelFile(file_path)
            df_rates = pd.read_excel(xls, "BaseRates")
            df_multipliers = pd.read_excel(xls, "Multipliers")

        # robust detection of column names
        city_col = next((c for c in df_rates.columns if 'ville' in str(c).lower()), df_rates.columns[0])
        base_col = next((c for c in df_rates.columns if 'base' in str(c).lower()), df_rates.columns[1])

        cities_data = {}
        for _, row in df_rates.iterrows():
            ville = row[city_col]
            base = row[base_col]
            brackets = {}
            for col in df_rates.columns:
                if col not in [city_col, base_col] and not pd.isna(row[col]):
                    try:
                        # Accept headers like "0 km", "10 km", "30" etc.
                        header = str(col)
                        header = header.replace(" km", "").strip()
                        cutoff = float(header)
                        brackets[cutoff] = row[col]
                    except (ValueError, TypeError):
                        continue
            cities_data[ville] = {"base": base, "brackets": brackets}

        # Multipliers
        multiplier_map = dict(zip(df_multipliers['Type'], df_multipliers['Value']))
        for key in ['non_normal', 'weekend', 'holiday']:
            multiplier_map.setdefault(key, 1.0)

        return cities_data, multiplier_map

    except Exception as exc:
        # final fallback sample data (prevents crash)
        st.warning(f"Erreur chargement paramètres: {exc}. Utilisation des valeurs par défaut.")
        return {
            "Tanger": {"base": 1.0, "brackets": {10: 6.5, 30: 5.5, 50: 4.5}},
            "Casablanca": {"base": 3.0, "brackets": {10: 7.5, 30: 6.0, 50: 5.0}}
        }, {'non_normal': 0.75, 'weekend': 0.93, 'holiday': 1.1}

# --- PDF GENERATION ---
def generate_pdf(context):
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("quote_template.html")
    html_out = template.render(context)
    
    # Create PDF in memory
    pdf_buffer = BytesIO()
    pisa.CreatePDF(BytesIO(html_out.encode("UTF-8")), pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

# Load parameters
cities_data, multipliers = load_parameters()

# --- USER INPUT ---
with st.container(border=True):
    st.header("🛠️ Configurer la simulation")
    col1, col2 = st.columns(2)
    with col1:
        ville = st.selectbox("Ville de départ", list(cities_data.keys()), help="Choisissez la ville d’origine du service")
        distance = st.number_input("Distance estimée (km)", min_value=0.1, value=34.0, step=0.5, format="%.1f", help="Estimation de la distance à parcourir")
        coeff_pression = st.select_slider("Urgence de la demande", options=[1.0, 1.5, 2.0], value=1.0, help="1.0 = Normal | 1.5 = Urgent | 2.0 = Critique")

    with col2:
        normal_shift = st.selectbox("Créneau horaire normal ?", ["Oui", "Non"], index=0, help="8h à 18h, du lundi au vendredi") == "Oui"
        weekend = st.selectbox("Service pendant le week-end ?", ["Non", "Oui"], index=0, help="Cochez si le service est requis un week-end") == "Oui"
        holiday = st.selectbox("Service un jour férié ?", ["Non", "Oui"], index=1, help="Cochez si le service est requis un jour férié") == "Oui"

# --- CALCULATION LOGIC ---
def get_tarif_km(distance, brackets):
    if not brackets: return 0.0
    sorted_brackets = sorted(brackets.items(), key=lambda x: x[0], reverse=True)
    for cutoff, rate in sorted_brackets:
        if distance >= cutoff:
            return rate
    return sorted_brackets[-1][1]

city_data = cities_data.get(ville, next(iter(cities_data.values())))

try:
    base_fixe = city_data["base"] * coeff_pression
    tarif_km = get_tarif_km(distance, city_data["brackets"])
    mult_total = 1.0
    if not normal_shift:
        mult_total *= multipliers.get('non_normal', 0.75)
    if weekend:
        mult_total *= multipliers.get('weekend', 0.93)
    if holiday:
        mult_total *= multipliers.get('holiday', 1.1)

    distance_cost = distance * tarif_km
    base_plus_distance = base_fixe + distance_cost
    subtotal = base_plus_distance * mult_total
    benef_supplier = subtotal * 0.10
    prix_transporteur = subtotal + benef_supplier
    benef_weego = prix_transporteur * 0.20
    prix_weego = prix_transporteur + benef_weego
except Exception as e:
    st.error(f"Erreur de calcul: {str(e)}")
    base_fixe = tarif_km = mult_total = distance_cost = base_plus_distance = subtotal = benef_supplier = prix_transporteur = benef_weego = prix_weego = 0

# Build context
context = {
    "date": datetime.now().strftime("%d/%m/%Y"),
    "ville": ville,
    "distance": f"{distance:.1f}",
    "coeff_pression": coeff_pression,
    "shift": "Oui" if normal_shift else "Non",
    "weekend": "Oui" if weekend else "Non",
    "holiday": "Oui" if holiday else "Non",
    "base_fixe": f"{base_fixe:.2f}",
    "tarif_km": f"{tarif_km:.2f}",
    "distance_cost": f"{distance_cost:.2f}",
    "base_plus_distance": f"{base_plus_distance:.2f}",
    "mult_total": f"{mult_total:.2f}",
    "subtotal": f"{subtotal:.2f}",
    "benef_supplier": f"{benef_supplier:.2f}",
    "prix_transporteur": f"{prix_transporteur:.2f}",
    "benef_weego": f"{benef_weego:.2f}",
    "prix_weego": f"{prix_weego:.2f}"
}

# --- OUTPUT ---
st.divider()
with st.container(border=True):
    st.subheader("📋 Récapitulatif des paramètres")
    cols = st.columns(4)
    cols[0].metric("Ville", ville)
    cols[1].metric("Distance", f"{distance} km")
    cols[2].metric("Urgence", coeff_pression)
    cols[3].metric("Multiplicateur", f"{mult_total:.2f}x")
    st.caption(f"Type de service: Shift {'Normal' if normal_shift else 'Spécial'} | Jour {'Férié' if holiday else 'Weekend' if weekend else 'Semaine'}")

with st.container(border=True):
    st.subheader("💰 Détail du prix")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Base fixe", f"{base_fixe:.2f} MAD")
        st.metric("Tarif/km", f"{tarif_km:.2f} MAD")
        st.metric("Coût distance", f"{distance_cost:.2f} MAD")
        st.metric("Avant multiplicateur", f"{base_plus_distance:.2f} MAD")
        st.metric("Après multiplicateur", f"{subtotal:.2f} MAD")
    with col2:
        st.write(f"**Base fixe :** {base_fixe:.2f} MAD")
        st.write(f"**Tarif/km :** {tarif_km:.2f} MAD × {distance} km = {distance_cost:.2f} MAD")
        st.write(f"**Avant multiplicateur :** {base_plus_distance:.2f} MAD")
        st.write(f"**Multiplicateur total :** {mult_total:.2f}x")
        st.write(f"**Après multiplicateur :** {subtotal:.2f} MAD")
        st.divider()
        st.write(f"**Bénéfice fournisseur (10%) :** {benef_supplier:.2f} MAD")
        st.write(f"**Prix transporteur :** {prix_transporteur:.2f} MAD")
        st.divider()
        st.write(f"**Bénéfice Weego (20%) :** {benef_weego:.2f} MAD")
        st.divider()
        st.success(f"🎯 **Prix final HT à proposer au client : {prix_weego:.2f} MAD**")

# SINGLE PDF DOWNLOAD SECTION
with st.container(border=True):
    st.subheader("📄 Télécharger le devis PDF")
    if st.button("Générer le devis"):
        try:
            pdf_buffer = generate_pdf(context)
            file_name = f"devis_weego_{ville.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            
            st.download_button(
                label="📥 Télécharger le devis",
                data=pdf_buffer,
                file_name=file_name,
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Erreur de génération PDF: {str(e)}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📘 Guide du simulateur")
    st.markdown("""
Bienvenue sur le simulateur de tarification **Weego**.

🧮 **Fonctionnement :**
- Choisissez les paramètres de transport (ville, distance, urgence…).
- Le simulateur applique automatiquement les tarifs et coefficients.
- Obtenez un **prix final HT** à proposer au client.

📂 **Modifier les tarifs ?**
- Modifiez le fichier `pricing_parameters.xlsx`
- Contactez l’équipe opérations pour le mettre à jour.

🔧 **À venir :**
- Historique des simulations
- Hébergement en ligne
- Génération de rapports
""")

    with st.expander("📊 Détail des coefficients", expanded=True):
        st.markdown(f"""
**Coefficient de pression:**
- 1.0 = Normal
- 1.5 = Urgent
- 2.0 = Critique

**Multiplicateurs supplémentaires :**
- Shift non-normal: ×{multipliers.get('non_normal', 0.75):.1f}
- Week-end: ×{multipliers.get('weekend', 0.93):.1f}
- Jour férié: ×{multipliers.get('holiday', 1.1):.1f}
""")
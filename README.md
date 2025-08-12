# Weego Pricing Simulator

A simple **Streamlit** web app that allows the Weego Ops team to calculate and simulate transport pricing based on adjustable parameters.

## 🚀 Features
- Upload & use **Excel pricing parameters**
- Interactive form for entering trip details
- Instant price calculation
- Generates downloadable **HTML quotes** using a template

## 📂 Project Structure

├── app.py # Main Streamlit app

├── pricing_parameters.xlsx # Base pricing data

├── quote_template.html # HTML template for quotes

├── requirements.txt # Python dependencies

├── .gitignore # Files to ignore in Git

└── README.md # Project documentation

## 🛠 Installation & Setup

**1. Clone the repository**
   
git clone https://github.com/youssefweego/weego-pricing-simulator.git
cd weego-pricing-simulator

**3. Create & activate a virtual environment (optional but recommended)**

python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

**5. Install dependencies**

pip install -r requirements.txt

**7. Run the app**

streamlit run app.py


## **📄 License**
This project is for internal Weego Ops use only. Not licensed for public distribution.

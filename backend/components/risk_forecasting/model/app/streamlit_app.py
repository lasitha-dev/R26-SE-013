import streamlit as st

st.set_page_config(
    page_title="FMD Early Warning System",
    page_icon="cow",
    layout="wide",
)

# Use modern Streamlit navigation API to explicitly define pages and hide the entrypoint
pages = {
    "Main Menu": [
        st.Page("views/1_Dashboard.py", title="Dashboard", icon="🏠"),
        st.Page("views/2_Predict_Outbreak.py", title="Predict Outbreak", icon="🔍"),
        st.Page("views/3_District_Forecast.py", title="District Forecast", icon="🗺️"),
        st.Page("views/4_Model_Performance.py", title="Model Performance", icon="📊"),
        st.Page("views/5_Explainability.py", title="Explainability", icon="🧠"),
        st.Page("views/6_Data_Explorer.py", title="Data Explorer", icon="📈"),
    ]
}

pg = st.navigation(pages)
pg.run()

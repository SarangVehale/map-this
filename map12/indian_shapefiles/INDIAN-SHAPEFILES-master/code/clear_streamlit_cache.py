import streamlit as st

if st.button('Clear Cache'):
    st.cache_data.clear()
    st.success('Cache successfully cleared!')


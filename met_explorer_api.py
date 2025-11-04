# met_explorer_api.py
import streamlit as st
import requests
from typing import List, Dict, Optional
import json
import io

MET_SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

st.set_page_config(page_title="MET Explorer (API-only)", layout="wide")

# -------------------------
# Session defaults
# -------------------------
if "favorites" not in st.session_state:
    st.session_state.favorites = {}
if "page" not in st.session_state:
    st.session_state.page = 1
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "per_page" not in st.session_state:
    st.session_state.per_page = 12

# -------------------------
# Sidebar controls
# -------------------------
st.sidebar.header("Search & Display")
query = st.sidebar.text_input("Search (title, artist, keyword)", key="query_input")
only_with_images = st.sidebar.checkbox("Only show artworks with images", value=True)
st.session_state.per_page = st.sidebar.selectbox("Results per page", [6, 9, 12, 18], index=2)
st.sidebar.markdown("---")
st.sidebar.header("Favorites")
if st.sidebar.button("Show favorites"):
    st.session_state.show_favorites = True
if st.sidebar.button("Clear favorites"):
    st.session_state.favorites = {}

# -------------------------
# Helpers (cached)
# -------------------------
@st.cache_data(ttl=3600)
def met_search(q: str, has_images: Optional[bool] = None) -> List[int]:
    if not q:
        return []
    params = {"q": q}
    if has_images is True:
        params["hasImages"] = "true"
    elif has_images is False:
        params["hasImages"] = "false"
    r = requests.get(MET_SEARCH_URL, params=params, timeout=15)
    r.raise_for_status()
    js = r.json()
    return js.get("objectIDs") or []

@st.cache_data(ttl=3600)
def met_get_object(object_id: int) -> Dict:
    r = requests.get(MET_OBJECT_URL.format(object_id), timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_image_bytes(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

# -------------------------
# Header / intro
# -------------------------
st.markdown("<h1 style='margin:0'>🖼️ MET Explorer (API-only)</h1>", unsafe_allow_html=True)
st.markdown("Search the Metropolitan Museum collection using their public API. No client-side hacks — reliable, deployable, simple.")

# Favorites view
if st.session_state.get("show_favorites"):
    st.header("❤️ Favorites")
    if not st.session_state.favorites:
        st.info("No favorites yet. Save favorites from the gallery.")
    else:
        for meta in st.session_state.favorites.values():
            st.markdown(f"**{meta.get('title')}** — {meta.get('artistDisplayName') or 'Unknown'}")
            st.markdown(f"[View on MET]({meta.get('objectURL')})")
        if st.button("Export favorites (JSON)"):
            b = json.dumps(list(st.session_state.favorites.values()), indent=2).encode("utf-8")
            st.download_button("Download JSON", data=b, file_name="met_favorites.json", mime="application/json")
    if st.button("Back to search"):
        st.session_state.show_favorites = False
    st.stop()

# Prompt if no query
if not query:
    st.info("Enter a search term in the sidebar (e.g., 'mona lisa', 'van gogh', 'landscape') and press Enter or click Search.")
    st.stop()

# Run search
with st.spinner("Searching MET collection..."):
    try:
        ids = met_search(query, has_images=(True if only_with_images else None))
    except Exception as e:
        st.error(f"Search failed: {e}")
        st.stop()

if not ids:
    st.warning("No results found. Try a different keyword or disable 'Only show artworks with images'.")
    st.stop()

# Pagination
per = st.session_state.per_page
total = len(ids)
total_pages = (total + per - 1) // per
page = st.session_state.page
# reset page if query changed
if query != st.session_state.last_query:
    st.session_state.page = 1
    page = 1
    st.session_state.last_query = query

start = (page - 1) * per
end = min(start + per, total)
page_ids = ids[start:end]

col_left, col_center, col_right = st.columns([1,2,1])
with col_left:
    if st.button("Previous") and page > 1:
        st.session_state.page = page - 1
with col_right:
    if st.button("Next") and page < total_pages:
        st.session_state.page = page + 1
with col_center:
    st.markdown(f"Page **{page}** / {total_pages} — {total} results")

# Gallery grid (uses 3 columns for balanced layout)
cols = st.columns(3)
for i, oid in enumerate(page_ids):
    col = cols[i % 3]
    with col:
        try:
            meta = met_get_object(oid)
        except Exception as e:
            st.write(f"Failed to load object {oid}: {e}")
            continue
        title = meta.get("title") or "Untitled"
        artist = meta.get("artistDisplayName") or "Unknown"
        img_url = meta.get("primaryImageSmall") or meta.get("primaryImage") or ""

        if img_url:
            st.image(img_url, use_column_width=True, clamp=False)
        else:
            st.markdown('<div style="height:160px;background:linear-gradient(180deg,#1b2730,#0f1315);display:flex;align-items:center;justify-content:center;color:#9aa3ad;border-radius:8px">No image</div>', unsafe_allow_html=True)

        st.markdown(f"**{title}**")
        st.markdown(f"*{artist}*")

        # Actions
        a, b = st.columns([1,1])
        with a:
            if st.button("Details", key=f"det_{oid}"):
                with st.modal("Artwork details"):
                    st.header(title)
                    if img_url:
                        st.image(img_url, use_column_width=True)
                        img_bytes = fetch_image_bytes(img_url)
                        if img_bytes:
                            st.download_button("Download image", data=img_bytes, file_name=f"met_{oid}.jpg", mime="image/jpeg")
                    st.markdown(f"**Artist:** {artist}")
                    st.markdown(f"**Date:** {meta.get('objectDate') or 'Unknown'}")
                    if meta.get("medium"):
                        st.markdown(f"**Medium:** {meta.get('medium')}")
                    if meta.get("department"):
                        st.markdown(f"**Department:** {meta.get('department')}")
                    if meta.get("objectURL"):
                        st.markdown(f"[View on MET website]({meta.get('objectURL')})")
                    if st.button("♥ Favorite" if oid not in st.session_state.favorites else "♥ Favorited (click to remove)"):
                        if oid in st.session_state.favorites:
                            st.session_state.favorites.pop(oid, None)
                            st.success("Removed from favorites")
                        else:
                            st.session_state.favorites[oid] = meta
                            st.success("Saved to favorites")
        with b:
            if img_url:
                img_bytes = fetch_image_bytes(img_url)
                if img_bytes:
                    st.download_button("Download", data=img_bytes, file_name=f"met_{oid}.jpg", mime="image/jpeg", key=f"dl_{oid}")

st.markdown("---")
st.markdown("Data from The Metropolitan Museum of Art Collection API — https://metmuseum.github.io/")

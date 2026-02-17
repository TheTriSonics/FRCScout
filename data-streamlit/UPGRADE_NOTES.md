# Streamlit App Upgrade Notes

## Date: 2026-02-16

### Summary
Successfully upgraded the Streamlit application from legacy dependencies (circa 2023) to modern versions compatible with Python 3.13.

### Key Version Updates

**Before:**
- streamlit: 1.42.2 (pinned with 100+ dependencies)
- pandas: 2.1.1
- numpy: 1.26.0
- Old, strictly pinned versions causing build failures

**After:**
- streamlit: 1.54.0 (latest)
- pandas: 2.3.3 (latest)
- numpy: 2.4.2 (latest)
- altair: 6.0.0 (latest)
- scikit-learn: 1.8.0 (latest)

### Changes Made

1. **requirements.txt**: Completely modernized and simplified
   - Removed 100+ strictly pinned dependencies
   - Kept only core dependencies with minimum version requirements
   - Uses `>=` constraints for better compatibility
   - Transitive dependencies are now managed automatically by pip

2. **Code Fixes**:
   - `scout.py`:
     - Removed invalid `persist` parameter from `@st.cache_data` decorators (not supported in modern Streamlit)
     - Added `ttl=300` (5 minutes) to all cache decorators to prevent recursion issues with argument hashing
     - Fixed `get_secret_key()` and `get_event_key()` to handle None values and return empty strings
     - Fixed `st.query_params` access to use dict-style access and convert to strings explicitly
   - All page files (`team_detail.py`, `clusters.py`, `pca.py`, `picklist.py`, `explore.py`, `match_breakdowns.py`):
     - Refactored to check for secret_key/event_key before loading data
     - Added warning messages when keys are not set
     - Prevented module-level data loading with empty keys (which caused recursion errors)
   - `pages/picklist.py`: Fixed zip objects to be lists for reusability
   - `pages/pca.py`: Replaced deprecated `np.matrix()` with `np.array()`

3. **Compatibility Verified**:
   - App starts successfully with no errors
   - All modern Streamlit APIs confirmed (no experimental/beta usage)
   - Uses `@st.cache_data` (modern caching)
   - Uses `st.navigation()` and `st.Page()` (modern multi-page)
   - Uses `st.query_params` (modern query parameter handling)

### Installation

To install dependencies:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the App

```bash
source .venv/bin/activate
streamlit run scout.py
```

### Issues Fixed

**RecursionError in Streamlit Caching:**
The original code had pages calling cached functions at module load time before secret_key/event_key were set. This caused Streamlit's cache hasher to encounter recursion issues when trying to hash complex arguments. Fixed by:
1. Adding TTL-based caching to reduce reliance on argument hashing
2. Ensuring all query_params and session_state values are converted to simple strings
3. Refactoring pages to check for keys before loading data
4. Adding early termination with warning messages when keys aren't set

### Notes

- Some `inplace=True` usage remains in pandas operations (discouraged but not deprecated)
- All deprecated APIs have been removed or replaced
- App is now fully compatible with Python 3.13 and modern package versions
- Cache TTL is set to 300 seconds (5 minutes) - adjust if needed for your use case

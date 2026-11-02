"""Team hometown coordinates for the app's Hometown game.

TBA gives each team a city, state_prov and country but no coordinates, so
they're looked up with the Open-Meteo geocoder (free, no key, GeoNames data)
and cached forever in the Places container, one doc per place. Only the US
and Canada are covered: the app only has map outlines for those.
"""

import re

import requests

GEOCODER = 'https://geocoding-api.open-meteo.com/v1/search'

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut',
    'DE': 'Delaware', 'DC': 'District of Columbia', 'FL': 'Florida',
    'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois',
    'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky',
    'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana',
    'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
    'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota',
    'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming',
}
CA_PROVINCES = {
    'AB': 'Alberta', 'BC': 'British Columbia', 'MB': 'Manitoba',
    'NB': 'New Brunswick', 'NL': 'Newfoundland and Labrador',
    'NS': 'Nova Scotia', 'NT': 'Northwest Territories', 'NU': 'Nunavut',
    'ON': 'Ontario', 'PE': 'Prince Edward Island', 'QC': 'Quebec',
    'SK': 'Saskatchewan', 'YT': 'Yukon',
}
_REGIONS = {'US': US_STATES, 'CA': CA_PROVINCES}
_COUNTRIES = {'usa': 'US', 'us': 'US', 'united states': 'US',
              'canada': 'CA', 'ca': 'CA'}


def _fold(text):
    return re.sub(r'[^a-z]', '', (text or '').lower()
                  .replace('é', 'e').replace('è', 'e'))


def country_code(country):
    return _COUNTRIES.get((country or '').strip().lower())


def state_code(country, state_prov):
    """'MI' for 'Michigan' or 'MI' in the US, 'ON' for 'Ontario', etc."""
    regions = _REGIONS.get(country or '')
    if not regions:
        return None
    s = (state_prov or '').strip()
    if s.upper() in regions:
        return s.upper()
    folded = _fold(s)
    for code, name in regions.items():
        if _fold(name) == folded:
            return code
    return None


def place_id(country, state, city):
    return f'{country}|{state}|{_fold(city)}'


def _city_names(city):
    """The city as TBA has it, then without 'Township' and the like."""
    city = (city or '').strip()
    names = [city]
    short = re.sub(r'\s+(charter\s+)?(township|twp\.?)$', '', city,
                   flags=re.I).strip()
    if short and short != city:
        names.append(short)
    # 'St Catharines' is 'St. Catharines' in GeoNames.
    for n in list(names):
        m = re.match(r'^(st\.?|saint)\s+(.*)$', n, flags=re.I)
        if m:
            names += [f'St. {m.group(2)}', f'Saint {m.group(2)}']
    return list(dict.fromkeys(names))


def geocode(country, state, city):
    """(lat, lng) of a US/Canadian city, or None if it can't be placed."""
    want = _fold(_REGIONS[country][state])
    for name in _city_names(city):
        try:
            r = requests.get(GEOCODER, params={
                'name': name, 'count': 20, 'countryCode': country,
                'language': 'en', 'format': 'json'}, timeout=10)
            r.raise_for_status()
        except requests.RequestException:
            return None
        for hit in r.json().get('results') or []:
            if _fold(hit.get('admin1')) == want:
                return hit['latitude'], hit['longitude']
    return None

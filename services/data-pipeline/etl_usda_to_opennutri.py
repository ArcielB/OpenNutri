#!/usr/bin/env python3
"""
ETL Script: Convert USDA FDC Foundation Food CSVs → OpenNutri Universal Schema
Uses Supabase REST API to bypass strict network block on port 5432/6543.
"""

import csv
import json
import os
import re
import uuid
import requests

# --- Config ---
CSV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 
    'FoodData_Central_foundation_food_csv_2025-12-18')

# Get variables from .env
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 
    'apps', 'expert-annotator', '.env')

def load_env():
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                env[k] = v
    return env

ENV = load_env()
SUPABASE_URL = ENV['VITE_SUPABASE_URL']
SUPABASE_KEY = ENV['VITE_SUPABASE_ANON_KEY'] # Using ANON key for REST since we bypass RLS for Postgres via service key if we had it. But wait, Anon key might hit RLS.
# Actually, the user can temporarily disable RLS for insertion or we can use the management API token. 
# Wait, let's use the Management API token to execute SQL directly instead of REST inserts, 
# OR we just insert over REST with the ANON key, as long as RLS allows inserts.

# Let's check the SQL schema we generated - we didn't add anon insert policies. 
# So we need to use a service role key. Let's just create an API token and pass it via environment variable in the run command.
SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', SUPABASE_KEY)

HEADERS = {
    'apikey': SERVICE_KEY,
    'Authorization': f'Bearer {SERVICE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal, resolution=merge-duplicates'
}

# Preparation state keywords
PREP_KEYWORDS = {
    'raw': 'raw', 'cooked': 'cooked', 'boiled': 'boiled', 'baked': 'baked',
    'roasted': 'roasted', 'fried': 'fried', 'grilled': 'grilled',
    'steamed': 'steamed', 'canned': 'canned', 'dried': 'dried',
    'frozen': 'frozen', 'smoked': 'smoked', 'pickled': 'pickled',
    'toasted': 'toasted', 'braised': 'braised', 'stewed': 'stewed',
    'microwaved': 'microwaved', 'broiled': 'broiled', 'simmered': 'simmered',
    'pan-fried': 'fried', 'deep-fried': 'fried',
}

def read_csv(filename):
    path = os.path.join(CSV_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def parse_preparation_state(description):
    desc_lower = description.lower()
    for keyword, state in PREP_KEYWORDS.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', desc_lower):
            return state
    return 'unspecified'

def rest_insert(table, data, conflict_col=None):
    """Insert data in batches via REST API"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if conflict_col:
        url += f"?on_conflict={conflict_col}"
    
    # REST API accepts max 1000 rows per batch
    batch_size = 500
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        response = requests.post(url, headers=HEADERS, json=batch)
        if response.status_code not in (200, 201):
            print(f"Error inserting into {table}: {response.text}")
            raise Exception("REST API Insert Failed")
        print(f"    Inserted {min(i+batch_size, len(data))}/{len(data)} into {table}", end='\r')
    print()

def main():
    print("=" * 60)
    print("OpenNutri ETL via REST API (Port 443)")
    print("=" * 60)

    print("\n[1/4] Reading CSV files...")
    foundation_foods = read_csv('foundation_food.csv')
    ff_ids = {row['fdc_id'] for row in foundation_foods}

    all_foods = read_csv('food.csv')
    food_lookup = {}
    for row in all_foods:
        if row['fdc_id'] in ff_ids:
            food_lookup[row['fdc_id']] = row

    categories = read_csv('food_category.csv')
    cat_lookup = {row['id']: row['description'] for row in categories}

    all_nutrients = read_csv('nutrient.csv')
    nutrient_lookup = {}
    skip_names = {'Fiber, crude (DO NOT USE - Archived)'}
    for row in all_nutrients:
        if row['name'] not in skip_names:
            nutrient_lookup[row['id']] = row

    print("  Reading food_nutrient.csv...")
    food_nutrients = []
    with open(os.path.join(CSV_DIR, 'food_nutrient.csv'), 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['fdc_id'] in ff_ids and row['nutrient_id'] in nutrient_lookup:
                food_nutrients.append(row)

    print("\n[2/4] Transforming data...")
    source_id = str(uuid.uuid4())
    source_data = [{
        'id': source_id,
        'source_type': 'EXTERNAL_DB',
        'source_name': 'USDA FoodData Central (Foundation Foods) 2025-12-18',
        'reference_uri': 'https://fdc.nal.usda.gov/',
        'source_metadata': {'version': '2025-12-18', 'dataset': 'foundation_food'}
    }]

    entities = []
    entity_id_map = {} # fdc_id -> UUID
    unique_entity_names = {} # canonical_name -> UUID
    for fdc_id, food in food_lookup.items():
        name = food['description']
        if name not in unique_entity_names:
            eid = str(uuid.uuid4())
            unique_entity_names[name] = eid
            entities.append({
                'id': eid,
                'canonical_name': name,
                'category': cat_lookup.get(food.get('food_category_id', ''), 'Unknown'),
            })
        else:
            eid = unique_entity_names[name]
        entity_id_map[fdc_id] = eid

    # Memory prep state lookup for claims
    entity_prep = {fdc_id: parse_preparation_state(food['description']) for fdc_id, food in food_lookup.items()}

    used_nutrient_ids = {row['nutrient_id'] for row in food_nutrients}
    nutrients_to_insert = []
    nutrient_id_map = {} # usda_id -> UUID
    unique_nutrient_names = {} # standard_name -> UUID
    for nid, ndata in nutrient_lookup.items():
        if nid in used_nutrient_ids:
            name = ndata['name']
            if name not in unique_nutrient_names:
                uid = str(uuid.uuid4())
                unique_nutrient_names[name] = uid
                nutrients_to_insert.append({
                    'id': uid,
                    'standard_name': name,
                    'description': f"Unit: {ndata['unit_name']}. USDA nutrient_nbr: {ndata['nutrient_nbr']}"
                })
            else:
                uid = unique_nutrient_names[name]
            nutrient_id_map[nid] = uid

    claims_data = []
    for fn in food_nutrients:
        fdc_id = fn['fdc_id']
        nutrient_usda_id = fn['nutrient_id']
        entity_uuid = entity_id_map.get(fdc_id)
        nutrient_uuid = nutrient_id_map.get(nutrient_usda_id)
        if not entity_uuid or not nutrient_uuid: continue

        try:
            amount = float(fn['amount'])
        except (ValueError, TypeError): continue

        unit = nutrient_lookup[nutrient_usda_id]['unit_name'].lower()

        sample_size = None
        if fn.get('data_points'):
            try: sample_size = int(fn['data_points'])
            except: pass

        metadata = {'usda_fdc_id': fdc_id, 'usda_nutrient_id': nutrient_usda_id}
        for key in ('min', 'max', 'median'):
            if fn.get(key):
                try: metadata[key] = float(fn[key])
                except: pass
        if fn.get('min_year_acquired'):
            metadata['min_year_acquired'] = fn['min_year_acquired']

        claims_data.append({
            'id': str(uuid.uuid4()),
            'entity_id': entity_uuid,
            'nutrient_id': nutrient_uuid,
            'source_id': source_id,
            'amount': amount,
            'unit': unit,
            'basis': 'per_100g',
            'preparation_state': entity_prep.get(fdc_id, 'unspecified'),
            'sample_size': sample_size,
            'confidence': 1.0,
            'extraction_method': 'ground_truth',
            'status': 'active',
            'metadata': metadata
        })

    print(f"  Entities: {len(entities)}")
    print(f"  Nutrients: {len(nutrients_to_insert)}")
    print(f"  Claims: {len(claims_data)}")

    print("\n[3/4] Uploading via REST API (HTTPS)...")
    rest_insert('sources', source_data, 'id')
    rest_insert('entities', entities, 'canonical_name')
    rest_insert('master_nutrients', nutrients_to_insert, 'standard_name')
    rest_insert('claims', claims_data, 'id')

    print("\n[4/4] Done!")

if __name__ == '__main__':
    main()

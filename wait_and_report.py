import time
import sys
from sqlalchemy import create_engine
import pandas as pd

engine = create_engine('postgresql+psycopg2://talash:talash@localhost:5433/talash')

def check_status():
    df = pd.read_sql('SELECT status FROM candidates', engine)
    return len(df) > 0 and all(s == 'completed' for s in df['status'])

print('Waiting for processing to finish...')
start = time.time()
while not check_status():
    if time.time() - start > 1200: # 20 mins timeout
        print('Timeout reached.')
        break
    time.sleep(10)

print('Processing finished. Final states:')
df = pd.read_sql('SELECT id, name, status FROM candidates', engine)
print(df)
print('\nErrors in Extraction Runs:')
errors = pd.read_sql('SELECT candidate_id, error_message FROM extraction_runs WHERE status != \'completed\'', engine)
print(errors if len(errors) > 0 else 'No errors recorded.')

from app.db import engine, Base
import app.models.models
print('Dropping tables...')
Base.metadata.drop_all(bind=engine)
print('Creating tables...')
Base.metadata.create_all(bind=engine)
print('Database flushed.')

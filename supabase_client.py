# supabase_client.py

import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY") or
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user(tg_id):
    return supabase.table("users").select("*").eq("tg_id", tg_id).execute().data

def create_user(tg_id, name):
    return supabase.table("users").insert({"tg_id": tg_id, "name": name}).execute()

def update_user(tg_id, **kwargs):
    return supabase.table("users").update(kwargs).eq("tg_id", tg_id).execute()

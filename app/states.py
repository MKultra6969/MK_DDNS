from aiogram.fsm.state import State, StatesGroup


class DDNSFSM(StatesGroup):
    add_provider_account_name = State()
    set_1984_key = State()
    set_cloudflare_token = State()
    add_1984_domain = State()
    add_cloudflare_name = State()
    add_cloudflare_proxied = State()

"""
USSD user warnings & guidance texts
Purpose: prevent user mistakes (98 loops, wrong input order)
Pilot: Angelopp / Village Marketplace
"""

# ---------- GLOBAL WARNINGS ----------

WARNING_MORE = (
    "NOTE:\n"
    "If you see MORE / 98, wait for the next screen.\n"
    "Do NOT retype the full code.\n"
)

WARNING_ONE_RUN = (
    "IMPORTANT:\n"
    "Complete this in ONE run.\n"
    "Only press numbers when asked.\n"
)

WARNING_NO_RESTART = (
    "Do not press 98 again.\n"
    "Do not restart unless the session ends.\n"
)

# ---------- ADD / UPDATE BUSINESS FLOW ----------

ADD_START_WARNING = (
    "CON Add / Update Business\n"
    "Please follow steps carefully.\n"
    "Do NOT press 98 again.\n"
)

CHOOSE_VILLAGE_HINT = (
    "Choose your village.\n"
    "Example: press 1 for Sega.\n"
)

ENTER_NAME_HINT = (
    "Enter business name ONLY.\n"
    "No numbers.\n"
    "Example: Mama Jane Shop\n"
)

CHOOSE_CATEGORY_HINT = (
    "Choose ONE category number.\n"
    "Do not type extra numbers.\n"
)

TRANSPORT_SUBCAT_HINT = (
    "Transport type:\n"
    "1 = Riders\n"
    "2 = Pickups\n"
    "3 = Lorries\n"
)

CONFIRM_HINT = (
    "Confirm details.\n"
    "Press 1 to SAVE.\n"
    "Press 2 to CANCEL.\n"
)

# ---------- ERROR MESSAGES ----------

ERROR_INVALID_OPTION = (
    "CON Invalid choice.\n"
    "Please press ONE valid number.\n"
    "0. Back\n"
)

ERROR_DONT_RETYPE_CODE = (
    "CON Please do NOT retype *98*.\n"
    "Just choose from the menu shown.\n"
)

ERROR_NAME_EMPTY = (
    "CON Business name missing.\n"
    "Please type the business name.\n"
)

ERROR_SESSION_RESET = (
    "CON Session restarted.\n"
    "Please start again calmly.\n"
)

# ---------- SUCCESS ----------

SUCCESS_SAVED = (
    "END Saved successfully!\n"
    "Your business is now visible.\n"
    "Thank you for using Angelopp.\n"
)

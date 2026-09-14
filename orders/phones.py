def phone_key(value):
    digits = "".join(character for character in str(value or "") if character.isdigit())
    # Los números mexicanos de diez dígitos y su versión +52 identifican al mismo cliente.
    return digits[2:] if len(digits) == 12 and digits.startswith("52") else digits

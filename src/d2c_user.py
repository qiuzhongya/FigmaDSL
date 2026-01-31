import d2c_config

def admin_verify(admin_name: str, admin_verify: str):
    if admin_name == d2c_config.AdminUser and admin_verify == d2c_config.AdminVerify:
        return True
    else:
        return False


def user_verify(input_name: str, database_name: str):
    if input_name == database_name :
        return True
    else:
        return False
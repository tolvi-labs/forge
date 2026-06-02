def sign_in(email, password):
    return {"email": email}


class AuthContext:
    def sign_out(self):
        return None

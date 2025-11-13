import base64


class Encrypt:
    """
    暗号化・複合化クラス
    """
    @staticmethod
    def b64_encode(text):
        """
        平文をbase64に変換する。
        """
        text_b = text.encode('ascii')
        b64_b = base64.b64encode(text_b)
        b64_t = b64_b.decode('ascii')
        return b64_t

    @staticmethod
    def b64_decode(text):
        """
        base64文字列を平文に変換する。
        """
        text_b = text.encode('ascii')
        decode_b = base64.b64decode(text_b)
        decode_t = decode_b.decode('ascii')
        return decode_t


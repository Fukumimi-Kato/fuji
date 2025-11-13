from django.core.management.base import BaseCommand
from django.core.mail import send_mail


class Command(BaseCommand):
    def handle(self, *args, **options):

        subject = "新規問い合わせが入りました"
        message = "施設様からチャットにて問い合わせが入っています。\nコントロールパネルにログインしご確認ください。"
        from_email = 'wada1@dan1.jp'  # 送信者
        recipient_list = ["harradyn@icloud.com"]  # 宛先リスト
        send_mail(subject, message, from_email, recipient_list)

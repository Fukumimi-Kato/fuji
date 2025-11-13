from django.db import models
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator, ASCIIUsernameValidator
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class UserManager(BaseUserManager):
    """
    Create and save user with email
    """
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        if not username:
            raise ValueError('The given username must be set')

        email = self.normalize_email(email)
        username = self.model.normalize_username(username)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('seq_order', 10)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Django標準のUserをベースにカスタマイズしたUserクラス
    """
    # username_validator = UnicodeUsernameValidator()
    # python3で半角英数のみ許容する場合はASCIIUsernameValidatorを用いる
    username_validator = ASCIIUsernameValidator()

    username = models.CharField(
        '顧客コード',
        max_length=50,
        unique=True,
        # help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        help_text='この項目は必須です。全角文字、半角英数字、@/./+/-/_ で50文字以下にしてください。',
        validators=[username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    company_name = models.CharField('会社名', max_length=150, blank=True, null=True)
    facility_name = models.CharField('施設名', max_length=150, blank=True)
    email = models.EmailField(
        _('email address'),
        help_text='メールアドレスは公開されません。',
        blank=True,
        null=True,
    )
    seq_order = models.IntegerField('表示順', blank=True, null=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        '契約中',
        default=True,
        help_text='現在利用中のお客様にチェックを入れます。解約の際、顧客コードは削除せずにこのチェックを外してください。 ',
    )
    invoice_pass = models.CharField('請求書参照用パスワード', max_length=16, blank=True, null=True)
    is_parent = models.BooleanField(
        '請求先親会社',
        default=False,
        help_text='請求書参照のみ可能な親会社である場合にチェックを入れます。注文等を行える顧客の場合は、このチェックを外してください。',
    )
    is_management = models.BooleanField(
        'システム利用会社管理者',
        default=False,
        help_text='管理情報に参照可能であるユーザー場合にチェックを入れます。施設、一般社員用のアカウントの場合は、このチェックを外してください。',
    )
    dry_cold_type_choices = (
        ('乾燥', '乾燥'),
        ('冷凍', '冷凍(直送)'),
        ('冷凍_談', '冷凍(談から送る)'),
    )
    dry_cold_type = models.CharField('乾燥・冷凍区分', max_length=8, choices=dry_cold_type_choices)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = UserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = verbose_name_plural = '顧客情報一覧'
        # abstract = True
        abstract = False

    def __str__(self):
        return self.facility_name

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    # first_nameとlast_nameに関する部分はコメントアウト
    # def get_full_name(self):
    #     """
    #     Return the first_name plus the last_name, with a space in between.
    #     """
    #     full_name = '%s %s' % (self.first_name, self.last_name)
    #     return full_name.strip()

    # def get_short_name(self):
    #     """Return the short name for the user."""
    #     return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

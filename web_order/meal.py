from .models import MealMaster

class MealUtil:
    @classmethod
    def get_name_list_without_snak(cls):
        """
        間食以外の食事区分を取得する
        """
        qs = MealMaster.objects.all().exclude(meal_name='間食').distinct().values_list('meal_name').order_by('seq_order')
        return [x[0] for x in qs]

    @classmethod
    def add_name_mark(cls, name: str):
        if name == '朝食':
            return '△' + name
        elif name == '昼食':
            return '〇' + name
        elif name == '夕食':
            return '□' + name
        else:
            return name

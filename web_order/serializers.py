from rest_framework import serializers
from .api_models import OperatedUnit, \
    OrderRateInput, EatingTimingOrder, ReferenceLogic, OrderRateOutput, UnitOrder, \
    MixRiceStructureInput, MixRiceStructureOutput, GosuLoggingInput


class OperatedUnitSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=150)
    status = serializers.CharField(max_length=8)


class EatingTimingSerializer(serializers.Serializer):
    eating_day = serializers.DateField()
    meal = serializers.CharField(max_length=8)
    quantity = serializers.FloatField()
    has_mix_rice = serializers.BooleanField()
    mix_rice_quantity = serializers.FloatField()
    liquid_quantity = serializers.FloatField()

    def create(self, validated_data):
        return EatingTimingOrder(**validated_data)

    def update(self, instance, validated_data):
        instance.eating_day = validated_data.get('eating_day', instance.eating_day)
        instance.meal = validated_data.get('meal', instance.meal)
        instance.quantity = validated_data.get('quantity', 0.0)
        instance.has_mix_rice = validated_data.get('has_mix_rice', False)
        return instance


class ReferenceLogicSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    week_day_settings = serializers.DictField(
        child=serializers.ListField(child=serializers.IntegerField())
    )
    meal_settings = serializers.DictField(
        child=serializers.CharField()
    )
    menu_settings = serializers.DictField(
        child=serializers.CharField()
    )
    from_day = serializers.DateField()
    to_day = serializers.DateField()

    def create(self, validated_data):
        return ReferenceLogic(**validated_data)


class OrderRateInputSerializer(serializers.Serializer):
    from_day = serializers.DateField()
    to_day = serializers.DateField()
    eating_list = serializers.ListField(
        child=EatingTimingSerializer(),
        required=False
    )
    logic_list = serializers.ListField(
        child=ReferenceLogicSerializer(),
        required=False
    )

    def create(self, validated_data):
        eating_data = validated_data.pop('eating_list')
        eatings = EatingTimingSerializer(many=True).create(eating_data)

        if 'logic_list' in validated_data:
            logic_data = validated_data.pop('logic_list')
            logics = ReferenceLogicSerializer(many=True).create(logic_data)
        else:
            logics = []
        return OrderRateInput(eating_list=eatings, logic_list=logics, **validated_data)

    def update(self, instance, validated_data):
        eating_data = validated_data.pop('eating_list')
        eating_list = EatingTimingOrderSerializer(many=True).update(instance.eating_list, eating_data)
        instance.from_day = validated_data.get('from_day', instance.title)
        instance.to_day = validated_data.get('to_day', instance.published_date)
        instance.mix_rice_rate = validated_data.get('mix_rice_rate', instance.isbn)
        instance.eating_list = eating_list
        return instance


class UnitOrderSerializer(serializers.Serializer):
    unit_number = serializers.IntegerField()
    unit_name = serializers.CharField(max_length=100)
    quantity = serializers.IntegerField()
    is_past_orders = serializers.BooleanField()

    def create(self, validated_data):
        return UnitOrder(**validated_data)


class OrderRateOutputSerializer(serializers.Serializer):
    eating_day = serializers.DateField()
    meal = serializers.CharField(max_length=8)
    rate = serializers.FloatField()
    soup_filling_rate = serializers.FloatField()
    total = serializers.IntegerField()
    gosu_total = serializers.FloatField()
    dry_gosu = serializers.FloatField()
    unit_order_list = serializers.ListField(
        child=UnitOrderSerializer()
    )

    needle_quantity_per_pack = serializers.FloatField()
    needle_packs = serializers.IntegerField()
    saved_packs = serializers.IntegerField()
    saved_1_packs = serializers.IntegerField()
    soft_orders = serializers.IntegerField()
    jelly_orders = serializers.IntegerField()
    mixer_orders = serializers.IntegerField()

    def create(self, validated_data):
        return OrderRateOutput(**validated_data)


class MixRiceStructureInputSerializer(serializers.Serializer):
    eating_day = serializers.DateField()
    meal = serializers.CharField(max_length=8)
    plate_list = serializers.ListField(
        child=serializers.CharField(max_length=100)
    )

    def create(self, validated_data):
        return MixRiceStructureInput(**validated_data)


class MixRiceStructureOutputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    plate_name = serializers.CharField(max_length=100)
    is_mix_rice = serializers.BooleanField()
    gosu_quantity = serializers.FloatField()
    gosu_liquid_quantity = serializers.FloatField()


class GosuLogInputSerializer(serializers.Serializer):
    eating_day = serializers.DateField()

    def create(self, validated_data):
        return GosuLoggingInput(**validated_data)


class GosuCalculationItemSerializer(serializers.Serializer):
    unit_number = serializers.IntegerField()
    unit_name = serializers.CharField(max_length=100)
    status = serializers.CharField(max_length=16)
    quantity = serializers.FloatField()


class GosuCalculationSerializer(serializers.Serializer):
    eating_day = serializers.DateField()
    needle_quantity = serializers.IntegerField()
    needle_orders = serializers.IntegerField()

    # 嚥下
    soft_quantity = serializers.IntegerField()
    jelly_quantity = serializers.IntegerField()
    mixer_quantity = serializers.IntegerField()

    unit_logging_list = serializers.ListField(
        child=GosuCalculationItemSerializer()
    )

    def create(self, validated_data):
        return GosuCalculationOutput(**validated_data)

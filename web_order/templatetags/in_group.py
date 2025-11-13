from django import template
register = template.Library()

@register.filter
def in_group(user, team_name):
    if user.groups.filter(name=team_name).exists():
        return True
    else:
        return False

import os


def parse(file_name):
    if not file_name: return {}
    parts = [group for group in os.path.basename(file_name).strip().split('.') if group not in ['txt', 'csv']]
    if len(parts) == 4:
        a, rup, b, version = parts
        keys = ('type', 'date', 'rup', 'x', 'version', 'path')
        dictionary = dict(zip(keys, (*a.split('_'), rup, b, version, os.path.dirname(file_name))))
        dictionary['plant'] = dictionary['rup'].split('_')[0] if dictionary['type'] == 'NEW' else dictionary['type']
        dictionary['type'] = 'OLD' if dictionary['type'] != 'NEW' else dictionary['type']
        return dictionary
    elif len(parts) == 5:
        a, rup, b, version, validation = parts
        keys = ('type', 'date', 'rup', 'x', 'version', 'path', 'validation')
        return dict(zip(keys, (*a.split('_'), rup, b, version, os.path.dirname(file_name), validation)))
    else:
        return {}


def file_name(parsed):
    return f"{parsed['plant']}_{parsed['date']}.{parsed['rup']}.{parsed['x']}.{parsed['version']}.txt"


def date(parsed):
    return parsed['date'][0:4], parsed['date'][4:6] # year, month


def path(parsed):
    return parsed['path']


def full_path(parsed):
    return os.path.join(path(parsed),file_name(parsed))


def is_relevant(parsed):
    return parsed['plant'] == 'UPR' # Check this out


def plant(parsed):
    return parsed['plant']


def x(parsed):
    return parsed['x']


def power_type(parsed):
    return parsed['x'].split('_', 1)[0]


def pretty_power_type(parsed):
    switcher = {
        'PVI': 'injection', # immissione
        'PVP': 'withdrawal', # prelievo
        # Misure energia elettrica prodotta per singola sezione, incentivazione GSE
        'PVG': 'generation', # generazione (da ignorare)
        'PVF': 'PVF',
        'ICV': 'ICV'
    }

    return switcher.get(power_type(parsed), '')


def is_withdrawal(parsed):
    return pretty_power_type(parsed) == 'withdrawal'


def is_injection(parsed):
    return pretty_power_type(parsed) == 'injection'


def sapr(parsed):
    if parsed.get('rup') == 'UPN_A221709_01':
        return 'A221709'
    else:
        return parsed['x'].split('_', 1)[1][0:7] if len(parsed['x'].split('_', 1)[1]) == 11 else ''


def section(parsed):
    return int(parsed[x].split('_')[-1])


def rup(parsed):
    return parsed['rup']


def unit(parsed):
    return rup(parsed) if not sapr(parsed) and len(rup(parsed).split('_')) == 4 else ''


def version(parsed):
    return int(parsed['version'])

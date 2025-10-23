 
def _get_number_split(num_str):
    # balance_str = columns[8].get('name')
    if num_str[-3:] == ".00":
        num = float(num_str.replace("$\xa0", "").replace(",", "").replace(".00", "").replace("\xa0₫", "").replace(".", "").split(' ')[0]) if num_str else 0
        symbol = num_str.split(' ')[1] if len(num_str.split(' ')) > 1 else ' '
        num_str = num_str.replace("$\xa0", "").replace(",", "").replace(".00", "").replace(".0", "").replace("\xa0₫", "").replace(".", "").split(' ')[0] if num_str else 0
    else:
        num = float(num_str.replace(",00", "").replace("$ ", "").replace("xa", "").replace("₫", "").replace("$", "").replace(".", "").replace("\xa0", "").replace(",", "").split(' ')[0]) if num_str else 0
        symbol = num_str.split(' ')[1] if len(num_str.split(' ')) > 1 else ' '
        num_str = num_str.replace("$ ", "").replace("xa", "").replace(",00", "").replace("$", "").replace(".", "").replace("₫", "").replace("\xa0", "").replace(",", "").split(' ')[0] if num_str else 0
    return num_str, num, symbol.replace("₫", "")


def set_column_widths(sheet, column_widths):
    for column, width in column_widths.items():
        sheet.set_column(column, width)
        

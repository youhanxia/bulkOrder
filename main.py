import csv
import sys

"""
Constants
"""
water_material_number = '2558'
water_pallet_per_load = 22
water_load_threshold = 18
other_pallet_per_load = 26


def calc_pallet(order, cases_per_pallet_dict):
    """
    calculate the number of loads given order.csv file and cases per pallet, pallets per load
    :param order: Original order as a list of dict
    :param cases_per_pallet_dict: a dict to lookup the number of cases per pallet for each item
    :return: the order with number of pallets required added to each item
    """
    order_in_pallets = []
    # no need to verify remainders
    for item in order:
        # for an item, calculate the number of pallets required in the order and add it into the return order
        item_in_pallets = dict(item)
        item_in_pallets['Pallets'] = item_in_pallets['Quantity'] / cases_per_pallet_dict[
            item_in_pallets['Material']]
        order_in_pallets.append(item_in_pallets)

    return order_in_pallets


# calculate the number of loads
# todo: adjust the result when some materials are out of stock
# def calc_load(order):
#     # check whether quantity is in the unit of pallets
#     if 'Pallets' not in order[0]:
#         print >> sys.stderr, 'calc_load ERROR: run calc_pallet first and pass in the return value as order_in_pallets'
#         return
#
#     # accumulators for water and everything else
#     water_num_pallets = 0
#     other_num_pallets = 0
#
#     # counting pallets
#     for item in order:
#         if item['Material'] == water_material_number:
#             water_num_pallets += item['Pallets']
#         else:
#             other_num_pallets += item['Pallets']
#
#     # accumulator for loads
#     num_loads = 0
#
#     # put into loads
#     # load water first
#     num_loads += water_num_pallets / water_pallet_per_load
#     water_num_pallets = water_num_pallets % water_pallet_per_load
#
#     # load the remaining water
#     if water_num_pallets > water_load_threshold:
#         num_loads += 1
#         other_num_pallets = other_num_pallets - (water_pallet_per_load - water_num_pallets) if other_num_pallets > (
#             water_pallet_per_load - water_num_pallets) else 0
#     elif water_num_pallets > 0:
#         num_loads += 1
#         other_num_pallets = other_num_pallets - (other_pallet_per_load - water_num_pallets) if other_num_pallets > (
#             other_pallet_per_load - water_num_pallets) else 0
#
#     # load other items
#     num_loads += other_num_pallets / other_pallet_per_load
#     remaining_pallets = other_num_pallets % other_pallet_per_load
#
#     return {'num_loads': num_loads, 'remaining_pallets': remaining_pallets}


def alloc_load(order, storage_dict):
    """
    Allocate the truck loads for a given order
    :param order: the order to be allocated
    :param storage_dict: two level dict where storage_dict[item][location] indicates
                         how many pallets of the item are stored at the location
    :return: num of loads in total, a list of all allocated items, a list of all unallocated items, a list of transfers
    """

    # check whether the number of pallets required is calculated for the order
    if 'Pallets' not in order[0]:
        print >> sys.stderr, 'calc_load ERROR: run calc_pallet first and pass in the return value as order_in_pallets'
        return

    # get water item from the order, None indicating no water in the order
    water_items = filter(lambda x: x['Material'] == water_material_number, order)
    water_item = water_items[0] if len(water_items) == 1 else None

    # items out of stock
    no_stock = []
    # dict items to allocate by locations
    unallocated_by_loc = {}
    # a list of unallocated items
    unallocated = list(order)
    for item in unallocated:
        # check if the item is short first
        if item['Material'] not in storage_dict:
            # field short is in the unit of pallets
            item['Short'] = item['Pallets']
            item['Unallocated Pallets'] = 0
            no_stock.append(item)
            continue
        total_stock = sum(storage_dict[item['Material']].values())
        if item['Pallets'] > total_stock:
            # field short is in the unit of pallets
            item['Short'] = item['Pallets'] - total_stock
            no_stock.append(item)
            item['Unallocated Pallets'] = total_stock
        else:
            item['Unallocated Pallets'] = item['Pallets']
            item['Short'] = 0

        item['Locations'] = storage_dict[item['Material']]
        for loc in item['Locations'].keys():
            if loc not in unallocated_by_loc:
                unallocated_by_loc[loc] = []
            unallocated_by_loc[loc].append(item)

    for item in no_stock:
        if item['Short'] == item['Pallets']:
            unallocated.remove(item)
            for loc in unallocated_by_loc:
                if item in unallocated_by_loc[loc]:
                    unallocated_by_loc[loc].remove(item)

    # a list of allocated items
    allocated = []
    # a list of transfers of items
    transfer = []

    # keep allocating until less than 1 load left
    load = 0
    while sum([item['Unallocated Pallets'] for item in unallocated]) >= (
            water_pallet_per_load if water_item and water_item[
                'Unallocated Pallets'] > water_load_threshold else other_pallet_per_load):
        # for each load to be allocated
        load += 1
        # choose a location where the load is allocated
        current_location = get_next_loc(unallocated_by_loc, water_item)
        space = other_pallet_per_load
        # console output
        print 'Truck number', load, 'is located at', current_location
        print '----------'
        # allocate water first if there is water remaining in the order
        if water_item:
            # load as many pallets of water as possible
            space = load_item(load, water_item, current_location, space, unallocated_by_loc,
                              allocated, unallocated, storage_dict)
            if water_item['Unallocated Pallets'] == 0:
                water_item = None
        while space > 0:
            # keep allocating until the the load is full
            if len(unallocated_by_loc[current_location]) > 0:
                # always load items available at the current location first
                item = unallocated_by_loc[current_location][0]
                space = load_item(load, item, current_location, space, unallocated_by_loc,
                                  allocated, unallocated, storage_dict)
            else:
                # if nothing to load at current location, we transfer
                num_items_at_locs = [(loc, sum([x['Unallocated Pallets'] for x in unallocated_by_loc[loc]])) for loc in
                                     unallocated_by_loc.keys()]
                # look for another location with unallocated items to transfer
                while True:
                    from_loc = min(num_items_at_locs, key=lambda x: x[1])
                    if len(unallocated_by_loc[from_loc[0]]):
                        from_loc = from_loc[0]
                        break
                    num_items_at_locs.remove(from_loc)
                item = unallocated_by_loc[from_loc][0]
                space = load_item(load, item, from_loc, space, unallocated_by_loc,
                                  allocated, unallocated, storage_dict, transfer=transfer, to_loc=current_location)
        print

    # return num of loads in total, a list of all allocated items, a list of all unallocated items, a list of transfers
    return {'num_loads': load, 'allocated': allocated, 'unallocated': no_stock + unallocated, 'transfer': transfer}


def load_item(load, item, location, space, unallocated_by_loc, allocated, unallocated,
              storage_dict, transfer=None, to_loc=None):
    """
    load item
    :param load: the id of current load
    :param item: item to allocate
    :param location: the location where the item comes from
    :param space: remaining space on the current load
    :param unallocated_by_loc: a dict which indexes unallocated items by locations
    :param allocated: a list of allocated items
    :param unallocated: a list of unallocated items
    :param storage_dict: two level dict where storage_dict[item][location] indicates
                         how many pallets of the item are stored at the location
    :param transfer: whether transfer is needed
    :param to_loc: the location to transfer to if transfer is needed
    :return: remaining space on the current load after loading the current item
    """
    # calculate how many pallets  to load, allocate as much as possible
    pallets_to_load = min([item['Unallocated Pallets'], space, storage_dict[item['Material']][location]])

    # subtract the number of pallets to load from Unallocated Quantity and storage, maintain space as well
    item['Unallocated Pallets'] -= pallets_to_load
    storage_dict[item['Material']][location] -= pallets_to_load
    if item['Material'] == water_material_number and pallets_to_load > water_load_threshold:
        space = water_pallet_per_load - pallets_to_load
    else:
        space -= pallets_to_load

    # maintain unallocated_by_loc if the item is completely allocated
    if item['Unallocated Pallets'] == 0:
        unallocated.remove(item)
        for loc in unallocated_by_loc:
            if item in unallocated_by_loc[loc]:
                unallocated_by_loc[loc].remove(item)

    # make an entry of the current item in allocated
    allocated_item = dict(item)
    allocated_item['Load'] = load
    allocated_item['Storage Location'] = location
    allocated_item['Allocated Pallets'] = pallets_to_load
    allocated_item['Transfer to'] = 'N/A'
    allocated.append(allocated_item)

    # console output
    print pallets_to_load, 'pallets of item number', item['Material'], 'are loaded',

    # make an entry in transfer if transfer is needed
    if transfer != None and to_loc != None:
        allocated_item['Transfer Pallets'] = pallets_to_load
        allocated_item['Transfer from'] = location
        allocated_item['Transfer to'] = to_loc
        transfer.append(allocated_item)
        # console output
        print ", transferred from", location
    else:
        # console output
        print

    return space


def get_next_loc(unallocated_by_loc, water_item=None):
    """
    find the location to allcate the next truck load
    :param unallocated_by_loc: a dict which indexes unallocated items by locations
    :param water_item: water item remaining in the order, None if no water remaining
    :return: the location chosen
    """
    # if water item is not allocated, always consider water first
    if water_item:
        # return the location with most water if water is not available from a single location
        if water_item['Unallocated Pallets'] > max(water_item['Locations'].values()):
            return max(water_item['Locations'].items, key=lambda x: x[1])[0]
        candidate_locs = filter(lambda x: water_item['Locations'][x] >= water_item['Unallocated Pallets'],
                                water_item['Locations'].keys())
    else:
        candidate_locs = unallocated_by_loc.keys()

    # sort everything within each dict entry with number of locations ascending and quantity descending
    # it is to decide the order of items to load
    for loc, items in unallocated_by_loc.items():
        items.sort(key=lambda x: (len(x['Locations']), -x['Unallocated Pallets']))

    # choose a critical location which has the most items only available there
    num_critical_items_at_locs = [(loc, sum([min([item['Unallocated Pallets'], item['Locations'][loc]]) for item in
                                             filter(lambda x: len(x['Locations']) == 1, unallocated_by_loc[loc])])) for
                                  loc in candidate_locs]
    next_loc = max(num_critical_items_at_locs, key=lambda x: x[1])

    if next_loc[1] == 0:
        # if there is no critical location, choose a location with the most remaining pallets instead
        num_pallets_at_locs = [(loc, len(unallocated_by_loc[loc])) for loc in candidate_locs]
        next_loc = max(num_pallets_at_locs, key=lambda x: x[1])

    return next_loc[0]


if __name__ == '__main__':

    # init constants and inputs
    water_material_number = '2558'
    water_pallet_per_load = 22
    water_load_threshold = 18
    other_pallet_per_load = 26

    # input files

    order_file = 'ColesPurchaseOrderR-56527656A.csv'
    cases_per_pallet_file = 'ActiveMaterial.csv'
    storage_file = 'PremMB52.csv'

    # order_file = 'toy_order.csv'
    # cases_per_pallet_file = 'ActiveMaterial.csv'
    # storage_file = 'toy_storage.csv'

    # output files
    complete_file = 'complete.csv'
    transfer_file = 'transfer.csv'
    incomplete_file = 'incomplete.csv'

    # read input data
    with open(order_file) as o_f:
        # has key: Purchase Order, Item Number, Material, Quantity, Unit of Measure, Description, Date
        order = list(csv.DictReader(o_f))  # todo: buggy if there are some formatting commands in the file

    for item in order:
        item['Quantity'] = int(item['Quantity'].replace(',', ''))  # special operation for comma separated numbers

    # a dict which key is "material number" and value is "cases per pallet"
    cases_per_pallet_dict = {}
    with open(cases_per_pallet_file) as cpp_f:
        for row in csv.DictReader(cpp_f):
            cases_per_pallet_dict[row['MATERIAL NUMBER']] = int(row['CASES PER PALLET'])

    storage_dict = {}
    with open(storage_file) as s_f:
        for row in csv.DictReader(s_f):
            material = row['Material']
            location = row['Storage Location']
            unrestricted = int(row['Unrestricted'].replace('.', ''))

            if not location:  # todo: there are '' location with 0 storage, maybe bad inputs, skip for now
                # if unrestricted != 0:
                #     print row
                continue

            if unrestricted == 0:
                # print row
                continue

            if material not in storage_dict:
                storage_dict[material] = {}
            if location not in storage_dict[material]:
                storage_dict[material][location] = 0
            # only consider the items which have cases per pallet info
            if material in cases_per_pallet_dict:
                # storage_dict[material][location] += unrestricted        # todo: some floats are cast to ints
                storage_dict[material][location] += unrestricted / cases_per_pallet_dict[material]

    # allocate loads

    # change the units
    order_edited = calc_pallet(order, cases_per_pallet_dict)

    result = alloc_load(order_edited, storage_dict)

    # Outputs
    print '----------Summary----------'
    print 'number of loads:', result['num_loads']
    print 'allocated items:', len(result['allocated'])
    print 'tansfers:', len(result['transfer'])
    print 'unallocated items:', len(result['unallocated'])

    order_fields = ['Purchase Order', 'Item Number', 'Material', 'Quantity', 'Unit of Measure', 'Description', 'Date']

    # write allocated order file
    with open(complete_file, 'w') as c_f:
        fieldnames = list(order_fields)
        fieldnames.extend(['Load', 'Storage Location', 'Allocated Pallets', 'Transfer to'])
        dw = csv.DictWriter(c_f, fieldnames=fieldnames, extrasaction='ignore')
        dw.writeheader()
        dw.writerows(result['allocated'])

    # write transfer file
    with open(transfer_file, 'w') as t_f:
        fieldnames = list(order_fields)
        fieldnames.extend(['Load', 'Transfer from', 'Transfer to', 'Transfer Pallets'])
        dw = csv.DictWriter(t_f, fieldnames=fieldnames, extrasaction='ignore')
        dw.writeheader()
        dw.writerows(result['transfer'])

    # write unallocated order file
    with open(incomplete_file, 'w') as ic_f:
        fieldnames = list(order_fields)
        fieldnames.extend(['Unallocated Pallets', 'Short'])
        dw = csv.DictWriter(ic_f, fieldnames=fieldnames, extrasaction='ignore')
        dw.writeheader()
        dw.writerows(result['unallocated'])

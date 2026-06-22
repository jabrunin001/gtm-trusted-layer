select account_id, net_new_arr, cycle_days
from {{ ref('int_bookings') }}

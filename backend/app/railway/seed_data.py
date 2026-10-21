"""Mock railway data.

Station codes and train numbers/names are real Indian Railways ones, but timings, distances,
running days, seat counts and fares are APPROXIMATE / SIMULATED for this demo.
Do not use this for real travel planning.
"""

# code, name, city, state
STATIONS = [
    ("CSMT", "Mumbai CSMT", "Mumbai", "Maharashtra"),
    ("DR", "Dadar", "Mumbai", "Maharashtra"),
    ("BCT", "Mumbai Central", "Mumbai", "Maharashtra"),
    ("LTT", "Lokmanya Tilak Terminus", "Mumbai", "Maharashtra"),
    ("TNA", "Thane", "Thane", "Maharashtra"),
    ("KYN", "Kalyan Jn", "Kalyan", "Maharashtra"),
    ("PNVL", "Panvel", "Panvel", "Maharashtra"),
    ("LNL", "Lonavala", "Lonavala", "Maharashtra"),
    ("PUNE", "Pune Jn", "Pune", "Maharashtra"),
    ("DD", "Daund Jn", "Daund", "Maharashtra"),
    ("SUR", "Solapur", "Solapur", "Maharashtra"),
    ("STR", "Satara", "Satara", "Maharashtra"),
    ("MRJ", "Miraj Jn", "Miraj", "Maharashtra"),
    ("KOP", "Kolhapur CSMT", "Kolhapur", "Maharashtra"),
    ("NK", "Nashik Road", "Nashik", "Maharashtra"),
    ("MMR", "Manmad Jn", "Manmad", "Maharashtra"),
    ("BSL", "Bhusaval Jn", "Bhusaval", "Maharashtra"),
    ("AK", "Akola Jn", "Akola", "Maharashtra"),
    ("BD", "Badnera Jn", "Amravati", "Maharashtra"),
    ("WR", "Wardha Jn", "Wardha", "Maharashtra"),
    ("NGP", "Nagpur Jn", "Nagpur", "Maharashtra"),
    ("G", "Gondia Jn", "Gondia", "Maharashtra"),
    ("RN", "Ratnagiri", "Ratnagiri", "Maharashtra"),
    ("MAO", "Madgaon Jn", "Madgaon", "Goa"),
    ("KRMI", "Karmali", "Panaji", "Goa"),
    ("ST", "Surat", "Surat", "Gujarat"),
    ("BRC", "Vadodara Jn", "Vadodara", "Gujarat"),
    ("ADI", "Ahmedabad Jn", "Ahmedabad", "Gujarat"),
    ("RTM", "Ratlam Jn", "Ratlam", "Madhya Pradesh"),
    ("ET", "Itarsi Jn", "Itarsi", "Madhya Pradesh"),
    ("BPL", "Bhopal Jn", "Bhopal", "Madhya Pradesh"),
    ("KOTA", "Kota Jn", "Kota", "Rajasthan"),
    ("NDLS", "New Delhi", "Delhi", "Delhi"),
    ("NZM", "Hazrat Nizamuddin", "Delhi", "Delhi"),
    ("UBL", "Hubballi Jn", "Hubballi", "Karnataka"),
    ("SBC", "KSR Bengaluru", "Bengaluru", "Karnataka"),
]

DAILY = "1111111"

# number, name, type, days_of_run (Mon..Sun), classes, stops[(code, arr, dep, day_offset, km)]
TRAINS = [
    ("12123", "Deccan Queen", "Superfast", DAILY, "CC,EC", [
        ("CSMT", None, "17:10", 0, 0), ("DR", "17:20", "17:22", 0, 9), ("KYN", "17:55", "17:57", 0, 54),
        ("LNL", "19:03", "19:05", 0, 128), ("PUNE", "20:25", None, 0, 192)]),
    ("12124", "Deccan Queen", "Superfast", DAILY, "CC,EC", [
        ("PUNE", None, "07:15", 0, 0), ("LNL", "08:03", "08:05", 0, 64), ("KYN", "09:15", "09:17", 0, 138),
        ("DR", "09:58", "10:00", 0, 183), ("CSMT", "10:25", None, 0, 192)]),
    ("12127", "Mumbai Pune Intercity", "Superfast", DAILY, "CC,EC", [
        ("CSMT", None, "06:40", 0, 0), ("DR", "06:50", "06:52", 0, 9), ("TNA", "07:12", "07:14", 0, 34),
        ("LNL", "08:35", "08:37", 0, 128), ("PUNE", "09:57", None, 0, 192)]),
    ("12128", "Pune Mumbai Intercity", "Superfast", DAILY, "CC,EC", [
        ("PUNE", None, "18:00", 0, 0), ("LNL", "18:48", "18:50", 0, 64), ("TNA", "20:15", "20:17", 0, 158),
        ("DR", "20:40", "20:42", 0, 183), ("CSMT", "21:05", None, 0, 192)]),
    ("11007", "Deccan Express", "Express", DAILY, "SL,3A,CC", [
        ("CSMT", None, "07:00", 0, 0), ("DR", "07:12", "07:15", 0, 9), ("KYN", "07:55", "08:00", 0, 54),
        ("LNL", "09:25", "09:28", 0, 128), ("PUNE", "11:05", None, 0, 192)]),
    ("12125", "Pragati Express", "Superfast", DAILY, "CC", [
        ("CSMT", None, "16:25", 0, 0), ("DR", "16:35", "16:37", 0, 9), ("TNA", "16:58", "17:00", 0, 34),
        ("LNL", "18:28", "18:30", 0, 128), ("PUNE", "19:50", None, 0, 192)]),
    ("12105", "Vidarbha Express", "Superfast", DAILY, "SL,3A,2A", [
        ("CSMT", None, "19:05", 0, 0), ("DR", "19:15", "19:17", 0, 9), ("KYN", "19:55", "19:58", 0, 54),
        ("NK", "22:38", "22:40", 0, 187), ("MMR", "23:55", "23:58", 0, 260), ("BSL", "02:10", "02:15", 1, 444),
        ("AK", "04:00", "04:05", 1, 584), ("BD", "05:15", "05:20", 1, 663), ("WR", "06:50", "06:55", 1, 758),
        ("NGP", "08:20", "08:30", 1, 837), ("G", "10:30", None, 1, 967)]),
    ("12106", "Vidarbha Express", "Superfast", DAILY, "SL,3A,2A", [
        ("G", None, "15:25", 0, 0), ("NGP", "17:05", "17:15", 0, 130), ("WR", "18:30", "18:33", 0, 209),
        ("BD", "20:00", "20:05", 0, 304), ("AK", "21:20", "21:25", 0, 383), ("BSL", "23:25", "23:30", 0, 523),
        ("MMR", "01:40", "01:43", 1, 707), ("NK", "02:55", "02:58", 1, 780), ("KYN", "05:45", "05:48", 1, 913),
        ("DR", "06:35", "06:37", 1, 958), ("CSMT", "07:05", None, 1, 967)]),
    ("12289", "Mumbai Nagpur Duronto", "Duronto", DAILY, "SL,3A,2A,1A", [
        ("CSMT", None, "20:15", 0, 0), ("NGP", "07:55", None, 1, 837)]),
    ("12290", "Nagpur Mumbai Duronto", "Duronto", DAILY, "SL,3A,2A,1A", [
        ("NGP", None, "20:40", 0, 0), ("CSMT", "08:15", None, 1, 837)]),
    ("12951", "Mumbai Rajdhani", "Rajdhani", DAILY, "3A,2A,1A", [
        ("BCT", None, "17:00", 0, 0), ("ST", "19:40", "19:45", 0, 263), ("BRC", "21:08", "21:13", 0, 392),
        ("RTM", "00:38", "00:43", 1, 653), ("KOTA", "03:15", "03:20", 1, 918), ("NDLS", "08:32", None, 1, 1386)]),
    ("12952", "New Delhi Rajdhani", "Rajdhani", DAILY, "3A,2A,1A", [
        ("NDLS", None, "16:55", 0, 0), ("KOTA", "21:30", "21:35", 0, 465), ("RTM", "00:50", "00:55", 1, 733),
        ("BRC", "04:15", "04:20", 1, 994), ("ST", "05:43", "05:48", 1, 1123), ("BCT", "08:35", None, 1, 1386)]),
    ("12137", "Punjab Mail", "Superfast", DAILY, "SL,3A,2A,1A", [
        ("CSMT", None, "19:35", 0, 0), ("DR", "19:47", "19:50", 0, 9), ("KYN", "20:35", "20:38", 0, 54),
        ("NK", "23:15", "23:20", 0, 187), ("MMR", "00:40", "00:45", 1, 260), ("BSL", "03:15", "03:20", 1, 444),
        ("ET", "08:50", "08:55", 1, 754), ("BPL", "10:35", "10:40", 1, 846), ("NDLS", "23:10", None, 1, 1546)]),
    ("11301", "Udyan Express", "Express", DAILY, "SL,3A,2A", [
        ("CSMT", None, "08:05", 0, 0), ("DR", "08:15", "08:18", 0, 9), ("KYN", "08:55", "08:58", 0, 54),
        ("PUNE", "11:45", "11:50", 0, 192), ("DD", "13:00", "13:05", 0, 268), ("SUR", "15:30", "15:35", 0, 455),
        ("SBC", "06:15", None, 1, 1153)]),
    ("12263", "Pune Nizamuddin Duronto", "Duronto", "0100100", "3A,2A,1A", [
        ("PUNE", None, "11:10", 0, 0), ("NZM", "05:55", None, 1, 1519)]),
    ("12051", "Dadar Madgaon Jan Shatabdi", "Jan Shatabdi", "1011111", "CC", [
        ("DR", None, "05:25", 0, 0), ("TNA", "05:50", "05:52", 0, 25), ("PNVL", "06:30", "06:35", 0, 54),
        ("RN", "10:20", "10:25", 0, 308), ("MAO", "14:45", None, 0, 582)]),
    ("22119", "Mumbai Karmali Tejas Express", "Tejas", "1110111", "CC,EC", [
        ("CSMT", None, "05:50", 0, 0), ("DR", "06:00", "06:02", 0, 9), ("TNA", "06:25", "06:27", 0, 34),
        ("PNVL", "07:00", "07:05", 0, 63), ("RN", "10:00", "10:05", 0, 317), ("KRMI", "13:40", None, 0, 557)]),
    ("12115", "Siddheshwar Express", "Superfast", DAILY, "SL,3A,2A,1A", [
        ("CSMT", None, "22:50", 0, 0), ("DR", "23:00", "23:03", 0, 9), ("KYN", "23:38", "23:41", 0, 54),
        ("PUNE", "02:25", "02:30", 1, 192), ("DD", "04:05", "04:10", 1, 268), ("SUR", "06:35", None, 1, 455)]),
    ("12116", "Siddheshwar Express", "Superfast", DAILY, "SL,3A,2A,1A", [
        ("SUR", None, "22:40", 0, 0), ("DD", "00:55", "01:00", 1, 187), ("PUNE", "02:45", "02:50", 1, 263),
        ("KYN", "05:45", "05:48", 1, 401), ("DR", "06:35", "06:38", 1, 446), ("CSMT", "07:10", None, 1, 455)]),
    ("17411", "Mahalaxmi Express", "Express", DAILY, "SL,3A,2A", [
        ("CSMT", None, "20:35", 0, 0), ("DR", "20:47", "20:50", 0, 9), ("KYN", "21:30", "21:33", 0, 54),
        ("PUNE", "00:40", "00:45", 1, 192), ("STR", "04:00", "04:03", 1, 315), ("MRJ", "06:20", "06:25", 1, 440),
        ("KOP", "07:35", None, 1, 487)]),
    ("17412", "Mahalaxmi Express", "Express", DAILY, "SL,3A,2A", [
        ("KOP", None, "20:25", 0, 0), ("MRJ", "21:15", "21:20", 0, 47), ("STR", "23:40", "23:43", 0, 172),
        ("PUNE", "03:10", "03:20", 1, 295), ("KYN", "06:25", "06:28", 1, 433), ("DR", "07:15", "07:18", 1, 478),
        ("CSMT", "07:55", None, 1, 487)]),
    ("12169", "Pune Solapur Intercity", "Superfast", DAILY, "CC", [
        ("PUNE", None, "18:15", 0, 0), ("DD", "19:25", "19:28", 0, 76), ("SUR", "22:20", None, 0, 263)]),
    ("12009", "Mumbai Ahmedabad Shatabdi", "Shatabdi", "1111110", "CC,EC", [
        ("BCT", None, "06:20", 0, 0), ("ST", "08:58", "09:00", 0, 263), ("BRC", "10:24", "10:29", 0, 392),
        ("ADI", "12:45", None, 0, 491)]),
]

# Simulated fare model (INR). Not the real IR fare table.
CLASS_INFO = {
    # class: (label, rate_per_km, reservation_charge, superfast_charge, coach_capacity)
    "SL": ("Sleeper", 0.55, 20, 30, 72),
    "3A": ("AC 3 Tier", 1.45, 40, 45, 64),
    "2A": ("AC 2 Tier", 2.10, 50, 45, 46),
    "1A": ("AC First Class", 3.50, 60, 75, 18),
    "CC": ("AC Chair Car", 1.30, 40, 45, 78),
    "EC": ("Executive Chair Car", 2.60, 60, 75, 56),
}
MIN_FARE = {"SL": 145, "3A": 385, "2A": 545, "1A": 905, "CC": 205, "EC": 415}
PREMIUM_TYPES = {"Rajdhani", "Duronto", "Shatabdi", "Tejas", "Jan Shatabdi"}  # catering etc. included
QUOTAS = {"GN": "General", "TQ": "Tatkal", "LD": "Ladies", "SS": "Senior Citizen"}

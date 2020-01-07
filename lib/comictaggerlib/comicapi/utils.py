# coding=utf-8
"""Some generic utilities"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os
import re
import platform
import locale
import codecs


class UtilsVars:
    already_fixed_encoding = False


def get_actual_preferred_encoding():
    preferred_encoding = locale.getpreferredencoding()
    if platform.system() == "Darwin":
        preferred_encoding = "utf-8"
    return preferred_encoding


def fix_output_encoding():
    if not UtilsVars.already_fixed_encoding:
        # this reads the environment and inits the right locale
        locale.setlocale(locale.LC_ALL, "")

        # try to make stdout/stderr encodings happy for unicode printing
        preferred_encoding = get_actual_preferred_encoding()
        sys.stdout = codecs.getwriter(preferred_encoding)(sys.stdout)
        sys.stderr = codecs.getwriter(preferred_encoding)(sys.stderr)
        UtilsVars.already_fixed_encoding = True


def get_recursive_filelist(pathlist):
    """Get a recursive list of of all files under all path items in the list"""

    filename_encoding = sys.getfilesystemencoding()
    filelist = []
    for p in pathlist:
        # if path is a folder, walk it recursively, and all files underneath
        if isinstance(p, str):
            # make sure string is unicode
            #p = p.decode(filename_encoding)  # , 'replace')
            pass
        elif not isinstance(p, str):
            # it's probably a QString
            p = str(p)

        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                for f in files:
                    if isinstance(f, str):
                        # make sure string is unicode
                        #f = f.decode(filename_encoding, 'replace')
                        pass
                    elif not isinstance(f, str):
                        # it's probably a QString
                        f = str(f)
                    filelist.append(os.path.join(root, f))
        else:
            filelist.append(p)

    return filelist


def listToString(l):
    string = ""
    if l is not None:
        for item in l:
            if len(string) > 0:
                string += ", "
            string += item
    return string


def addtopath(dirname):
    if dirname is not None and dirname != "":

        # verify that path doesn't already contain the given dirname
        tmpdirname = re.escape(dirname)
        pattern = r"{sep}{dir}$|^{dir}{sep}|{sep}{dir}{sep}|^{dir}$".format(
            dir=tmpdirname,
            sep=os.pathsep)

        match = re.search(pattern, os.environ['PATH'])
        if not match:
            os.environ['PATH'] = dirname + os.pathsep + os.environ['PATH']


def which(program):
    """Returns path of the executable, if it exists"""

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def removearticles(text):
    text = text.lower()
    articles = ['and', 'a', '&', 'issue', 'the']
    newText = ''
    for word in text.split(' '):
        if word not in articles:
            newText += word + ' '

    newText = newText[:-1]

    # now get rid of some other junk
    newText = newText.replace(":", "")
    newText = newText.replace(",", "")
    newText = newText.replace("-", " ")

    # since the CV API changed, searches for series names with periods
    # now explicitly require the period to be in the search key,
    # so the line below is removed (for now)
    #newText = newText.replace(".", "")

    return newText


def unique_file(file_name):
    counter = 1
    # returns ('/path/file', '.ext')
    file_name_parts = os.path.splitext(file_name)
    while True:
        if not os.path.lexists(file_name):
            return file_name
        file_name = file_name_parts[
            0] + ' (' + str(counter) + ')' + file_name_parts[1]
        counter += 1


# -o- coding: utf-8 -o-
# ISO639 python dict
# official list in http://www.loc.gov/standards/iso639-2/php/code_list.php

lang_dict = {
    'ab': 'Abkhaz',
    'aa': 'Afar',
    'af': 'Afrikaans',
    'ak': 'Akan',
    'sq': 'Albanian',
    'am': 'Amharic',
    'ar': 'Arabic',
    'an': 'Aragonese',
    'hy': 'Armenian',
    'as': 'Assamese',
    'av': 'Avaric',
    'ae': 'Avestan',
    'ay': 'Aymara',
    'az': 'Azerbaijani',
    'bm': 'Bambara',
    'ba': 'Bashkir',
    'eu': 'Basque',
    'be': 'Belarusian',
    'bn': 'Bengali',
    'bh': 'Bihari',
    'bi': 'Bislama',
    'bs': 'Bosnian',
    'br': 'Breton',
    'bg': 'Bulgarian',
    'my': 'Burmese',
    'ca': 'Catalan; Valencian',
    'ch': 'Chamorro',
    'ce': 'Chechen',
    'ny': 'Chichewa; Chewa; Nyanja',
    'zh': 'Chinese',
    'cv': 'Chuvash',
    'kw': 'Cornish',
    'co': 'Corsican',
    'cr': 'Cree',
    'hr': 'Croatian',
    'cs': 'Czech',
    'da': 'Danish',
    'dv': 'Divehi; Maldivian;',
    'nl': 'Dutch',
    'dz': 'Dzongkha',
    'en': 'English',
    'eo': 'Esperanto',
    'et': 'Estonian',
    'ee': 'Ewe',
    'fo': 'Faroese',
    'fj': 'Fijian',
    'fi': 'Finnish',
    'fr': 'French',
    'ff': 'Fula',
    'gl': 'Galician',
    'ka': 'Georgian',
    'de': 'German',
    'el': 'Greek, Modern',
    'gn': 'Guaraní',
    'gu': 'Gujarati',
    'ht': 'Haitian',
    'ha': 'Hausa',
    'he': 'Hebrew (modern)',
    'hz': 'Herero',
    'hi': 'Hindi',
    'ho': 'Hiri Motu',
    'hu': 'Hungarian',
    'ia': 'Interlingua',
    'id': 'Indonesian',
    'ie': 'Interlingue',
    'ga': 'Irish',
    'ig': 'Igbo',
    'ik': 'Inupiaq',
    'io': 'Ido',
    'is': 'Icelandic',
    'it': 'Italian',
    'iu': 'Inuktitut',
    'ja': 'Japanese',
    'jv': 'Javanese',
    'kl': 'Kalaallisut',
    'kn': 'Kannada',
    'kr': 'Kanuri',
    'ks': 'Kashmiri',
    'kk': 'Kazakh',
    'km': 'Khmer',
    'ki': 'Kikuyu, Gikuyu',
    'rw': 'Kinyarwanda',
    'ky': 'Kirghiz, Kyrgyz',
    'kv': 'Komi',
    'kg': 'Kongo',
    'ko': 'Korean',
    'ku': 'Kurdish',
    'kj': 'Kwanyama, Kuanyama',
    'la': 'Latin',
    'lb': 'Luxembourgish',
    'lg': 'Luganda',
    'li': 'Limburgish',
    'ln': 'Lingala',
    'lo': 'Lao',
    'lt': 'Lithuanian',
    'lu': 'Luba-Katanga',
    'lv': 'Latvian',
    'gv': 'Manx',
    'mk': 'Macedonian',
    'mg': 'Malagasy',
    'ms': 'Malay',
    'ml': 'Malayalam',
    'mt': 'Maltese',
    'mi': 'Māori',
    'mr': 'Marathi (Marāṭhī)',
    'mh': 'Marshallese',
    'mn': 'Mongolian',
    'na': 'Nauru',
    'nv': 'Navajo, Navaho',
    'nb': 'Norwegian Bokmål',
    'nd': 'North Ndebele',
    'ne': 'Nepali',
    'ng': 'Ndonga',
    'nn': 'Norwegian Nynorsk',
    'no': 'Norwegian',
    'ii': 'Nuosu',
    'nr': 'South Ndebele',
    'oc': 'Occitan',
    'oj': 'Ojibwe, Ojibwa',
    'cu': 'Old Church Slavonic',
    'om': 'Oromo',
    'or': 'Oriya',
    'os': 'Ossetian, Ossetic',
    'pa': 'Panjabi, Punjabi',
    'pi': 'Pāli',
    'fa': 'Persian',
    'pl': 'Polish',
    'ps': 'Pashto, Pushto',
    'pt': 'Portuguese',
    'qu': 'Quechua',
    'rm': 'Romansh',
    'rn': 'Kirundi',
    'ro': 'Romanian, Moldavan',
    'ru': 'Russian',
    'sa': 'Sanskrit (Saṁskṛta)',
    'sc': 'Sardinian',
    'sd': 'Sindhi',
    'se': 'Northern Sami',
    'sm': 'Samoan',
    'sg': 'Sango',
    'sr': 'Serbian',
    'gd': 'Scottish Gaelic',
    'sn': 'Shona',
    'si': 'Sinhala, Sinhalese',
    'sk': 'Slovak',
    'sl': 'Slovene',
    'so': 'Somali',
    'st': 'Southern Sotho',
    'es': 'Spanish; Castilian',
    'su': 'Sundanese',
    'sw': 'Swahili',
    'ss': 'Swati',
    'sv': 'Swedish',
    'ta': 'Tamil',
    'te': 'Telugu',
    'tg': 'Tajik',
    'th': 'Thai',
    'ti': 'Tigrinya',
    'bo': 'Tibetan',
    'tk': 'Turkmen',
    'tl': 'Tagalog',
    'tn': 'Tswana',
    'to': 'Tonga',
    'tr': 'Turkish',
    'ts': 'Tsonga',
    'tt': 'Tatar',
    'tw': 'Twi',
    'ty': 'Tahitian',
    'ug': 'Uighur, Uyghur',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'uz': 'Uzbek',
    've': 'Venda',
    'vi': 'Vietnamese',
    'vo': 'Volapük',
    'wa': 'Walloon',
    'cy': 'Welsh',
    'wo': 'Wolof',
    'fy': 'Western Frisian',
    'xh': 'Xhosa',
    'yi': 'Yiddish',
    'yo': 'Yoruba',
    'za': 'Zhuang, Chuang',
    'zu': 'Zulu',
}


countries = [
    ('AF', 'Afghanistan'),
    ('AL', 'Albania'),
    ('DZ', 'Algeria'),
    ('AS', 'American Samoa'),
    ('AD', 'Andorra'),
    ('AO', 'Angola'),
    ('AI', 'Anguilla'),
    ('AQ', 'Antarctica'),
    ('AG', 'Antigua And Barbuda'),
    ('AR', 'Argentina'),
    ('AM', 'Armenia'),
    ('AW', 'Aruba'),
    ('AU', 'Australia'),
    ('AT', 'Austria'),
    ('AZ', 'Azerbaijan'),
    ('BS', 'Bahamas'),
    ('BH', 'Bahrain'),
    ('BD', 'Bangladesh'),
    ('BB', 'Barbados'),
    ('BY', 'Belarus'),
    ('BE', 'Belgium'),
    ('BZ', 'Belize'),
    ('BJ', 'Benin'),
    ('BM', 'Bermuda'),
    ('BT', 'Bhutan'),
    ('BO', 'Bolivia'),
    ('BA', 'Bosnia And Herzegowina'),
    ('BW', 'Botswana'),
    ('BV', 'Bouvet Island'),
    ('BR', 'Brazil'),
    ('BN', 'Brunei Darussalam'),
    ('BG', 'Bulgaria'),
    ('BF', 'Burkina Faso'),
    ('BI', 'Burundi'),
    ('KH', 'Cambodia'),
    ('CM', 'Cameroon'),
    ('CA', 'Canada'),
    ('CV', 'Cape Verde'),
    ('KY', 'Cayman Islands'),
    ('CF', 'Central African Rep'),
    ('TD', 'Chad'),
    ('CL', 'Chile'),
    ('CN', 'China'),
    ('CX', 'Christmas Island'),
    ('CC', 'Cocos Islands'),
    ('CO', 'Colombia'),
    ('KM', 'Comoros'),
    ('CG', 'Congo'),
    ('CK', 'Cook Islands'),
    ('CR', 'Costa Rica'),
    ('CI', 'Cote D`ivoire'),
    ('HR', 'Croatia'),
    ('CU', 'Cuba'),
    ('CY', 'Cyprus'),
    ('CZ', 'Czech Republic'),
    ('DK', 'Denmark'),
    ('DJ', 'Djibouti'),
    ('DM', 'Dominica'),
    ('DO', 'Dominican Republic'),
    ('TP', 'East Timor'),
    ('EC', 'Ecuador'),
    ('EG', 'Egypt'),
    ('SV', 'El Salvador'),
    ('GQ', 'Equatorial Guinea'),
    ('ER', 'Eritrea'),
    ('EE', 'Estonia'),
    ('ET', 'Ethiopia'),
    ('FK', 'Falkland Islands (Malvinas)'),
    ('FO', 'Faroe Islands'),
    ('FJ', 'Fiji'),
    ('FI', 'Finland'),
    ('FR', 'France'),
    ('GF', 'French Guiana'),
    ('PF', 'French Polynesia'),
    ('TF', 'French S. Territories'),
    ('GA', 'Gabon'),
    ('GM', 'Gambia'),
    ('GE', 'Georgia'),
    ('DE', 'Germany'),
    ('GH', 'Ghana'),
    ('GI', 'Gibraltar'),
    ('GR', 'Greece'),
    ('GL', 'Greenland'),
    ('GD', 'Grenada'),
    ('GP', 'Guadeloupe'),
    ('GU', 'Guam'),
    ('GT', 'Guatemala'),
    ('GN', 'Guinea'),
    ('GW', 'Guinea-bissau'),
    ('GY', 'Guyana'),
    ('HT', 'Haiti'),
    ('HN', 'Honduras'),
    ('HK', 'Hong Kong'),
    ('HU', 'Hungary'),
    ('IS', 'Iceland'),
    ('IN', 'India'),
    ('ID', 'Indonesia'),
    ('IR', 'Iran'),
    ('IQ', 'Iraq'),
    ('IE', 'Ireland'),
    ('IL', 'Israel'),
    ('IT', 'Italy'),
    ('JM', 'Jamaica'),
    ('JP', 'Japan'),
    ('JO', 'Jordan'),
    ('KZ', 'Kazakhstan'),
    ('KE', 'Kenya'),
    ('KI', 'Kiribati'),
    ('KP', 'Korea (North)'),
    ('KR', 'Korea (South)'),
    ('KW', 'Kuwait'),
    ('KG', 'Kyrgyzstan'),
    ('LA', 'Laos'),
    ('LV', 'Latvia'),
    ('LB', 'Lebanon'),
    ('LS', 'Lesotho'),
    ('LR', 'Liberia'),
    ('LY', 'Libya'),
    ('LI', 'Liechtenstein'),
    ('LT', 'Lithuania'),
    ('LU', 'Luxembourg'),
    ('MO', 'Macau'),
    ('MK', 'Macedonia'),
    ('MG', 'Madagascar'),
    ('MW', 'Malawi'),
    ('MY', 'Malaysia'),
    ('MV', 'Maldives'),
    ('ML', 'Mali'),
    ('MT', 'Malta'),
    ('MH', 'Marshall Islands'),
    ('MQ', 'Martinique'),
    ('MR', 'Mauritania'),
    ('MU', 'Mauritius'),
    ('YT', 'Mayotte'),
    ('MX', 'Mexico'),
    ('FM', 'Micronesia'),
    ('MD', 'Moldova'),
    ('MC', 'Monaco'),
    ('MN', 'Mongolia'),
    ('MS', 'Montserrat'),
    ('MA', 'Morocco'),
    ('MZ', 'Mozambique'),
    ('MM', 'Myanmar'),
    ('NA', 'Namibia'),
    ('NR', 'Nauru'),
    ('NP', 'Nepal'),
    ('NL', 'Netherlands'),
    ('AN', 'Netherlands Antilles'),
    ('NC', 'New Caledonia'),
    ('NZ', 'New Zealand'),
    ('NI', 'Nicaragua'),
    ('NE', 'Niger'),
    ('NG', 'Nigeria'),
    ('NU', 'Niue'),
    ('NF', 'Norfolk Island'),
    ('MP', 'Northern Mariana Islands'),
    ('NO', 'Norway'),
    ('OM', 'Oman'),
    ('PK', 'Pakistan'),
    ('PW', 'Palau'),
    ('PA', 'Panama'),
    ('PG', 'Papua New Guinea'),
    ('PY', 'Paraguay'),
    ('PE', 'Peru'),
    ('PH', 'Philippines'),
    ('PN', 'Pitcairn'),
    ('PL', 'Poland'),
    ('PT', 'Portugal'),
    ('PR', 'Puerto Rico'),
    ('QA', 'Qatar'),
    ('RE', 'Reunion'),
    ('RO', 'Romania'),
    ('RU', 'Russian Federation'),
    ('RW', 'Rwanda'),
    ('KN', 'Saint Kitts And Nevis'),
    ('LC', 'Saint Lucia'),
    ('VC', 'St Vincent/Grenadines'),
    ('WS', 'Samoa'),
    ('SM', 'San Marino'),
    ('ST', 'Sao Tome'),
    ('SA', 'Saudi Arabia'),
    ('SN', 'Senegal'),
    ('SC', 'Seychelles'),
    ('SL', 'Sierra Leone'),
    ('SG', 'Singapore'),
    ('SK', 'Slovakia'),
    ('SI', 'Slovenia'),
    ('SB', 'Solomon Islands'),
    ('SO', 'Somalia'),
    ('ZA', 'South Africa'),
    ('ES', 'Spain'),
    ('LK', 'Sri Lanka'),
    ('SH', 'St. Helena'),
    ('PM', 'St.Pierre'),
    ('SD', 'Sudan'),
    ('SR', 'Suriname'),
    ('SZ', 'Swaziland'),
    ('SE', 'Sweden'),
    ('CH', 'Switzerland'),
    ('SY', 'Syrian Arab Republic'),
    ('TW', 'Taiwan'),
    ('TJ', 'Tajikistan'),
    ('TZ', 'Tanzania'),
    ('TH', 'Thailand'),
    ('TG', 'Togo'),
    ('TK', 'Tokelau'),
    ('TO', 'Tonga'),
    ('TT', 'Trinidad And Tobago'),
    ('TN', 'Tunisia'),
    ('TR', 'Turkey'),
    ('TM', 'Turkmenistan'),
    ('TV', 'Tuvalu'),
    ('UG', 'Uganda'),
    ('UA', 'Ukraine'),
    ('AE', 'United Arab Emirates'),
    ('UK', 'United Kingdom'),
    ('US', 'United States'),
    ('UY', 'Uruguay'),
    ('UZ', 'Uzbekistan'),
    ('VU', 'Vanuatu'),
    ('VA', 'Vatican City State'),
    ('VE', 'Venezuela'),
    ('VN', 'Viet Nam'),
    ('VG', 'Virgin Islands (British)'),
    ('VI', 'Virgin Islands (U.S.)'),
    ('EH', 'Western Sahara'),
    ('YE', 'Yemen'),
    ('YU', 'Yugoslavia'),
    ('ZR', 'Zaire'),
    ('ZM', 'Zambia'),
    ('ZW', 'Zimbabwe')
]


def getLanguageDict():
    return lang_dict


def getLanguageFromISO(iso):
    if iso is None:
        return None
    else:
        return lang_dict[iso]

# 00 Весь Импорт
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta # - продвинутые операции с датами (добавление месяцев)
import pandas as pd
import locale   # для русификации названия месецев
locale.setlocale(locale.LC_TIME, 'Russian')
from typing import Dict, List, Tuple, Any # возможность аннотирования типов в Python
from tabulate import tabulate   # для оформления в табличку
# from collections import defaultdict
# --------------------------------------------------------------

#   01
class Input_data:
    # 01    Ставки рефинансирования ЦБ РФ
    stavka_file = 'stavka_CB_1.xlsx'  # Путь к файлу со ставками ЦБ (Дата: значение ставки (число)), в будущем будет парсинг с сайта

    # 02    Сумма для расчета (Долг)
      # 02.01     (Дата)
    dolg_period = 'май 2021' # ФОРМАТ: "Январь 2024". Вводится неоплаченый период за который возник долг
      # 02.02     (Сумма)
    dolg_sum = round(float(5684.03), 2) # ФОРМАТ: "11 524.25". Вводится сумма долга (здесь - это остаточная сумма)
    # ЕЩЕ нужно сделать функцию, которая будет уменьшать сумму долга в случае частичной или полной оплаты - по алгоритму
    # В дальнейшем ввод сумм будет иметь иной формат, скорее всего в виде ЗАГРУЗКИ таблицы Excel

    # Конечная дата по которую нужно расчитать пени
    # end_date = '2023.02.28'   # Конечная дата рассматриваемого периода

    # -----------------------------
    # 00 02         УСЛОВИЯ (те что определяют расчеты, но их можно поменять)

    lok_stavka_CB = float(9.5) # Законодательное ограничение ставки для целей начисления пеней

    # Законодательные условия расчета ставки пеней
    st_300 = int(300) # Это значение на которое делится СТАВКА РЕФ. (с 31 по 90 день)
    st_130 = int(130) # Это значение на которое делится СТАВКА РЕФ. (с 91 дня)

    # Объявление условий по применению ставок (делителей) к расчету пеней
    period_1 = 10
    period_2 = 30
    period_3 = 90

    # Мораторий на начисление пеней. Это периоды, которые нужно исключить из расчета ставки пеней.
    moratoryi_1 = ['2020.04.01', '2020.12.31']
    moratoryi_2 = ['2022.04.01', '2022.09.30']
# ----------------------------------------------------------------------------

#   02
#     КЛАСС отвечающий за подготовку данных для будущих расчетов: Обработка, приведение к нужным форматам

class Prepare_data:
    def __init__(self, end_date):
        self.file_path = Input_data().stavka_file  # Путь к файлу (Задается изначально... его нет смысла вводить, но можно оставить возможность поправить пользователю, в своих целях)
        self.dolg_period = Input_data().dolg_period # Ссылка на дату, с которой начинается отсчет всех расчетов - дата старта расчетов
        self.dolg_sum = Input_data().dolg_sum # Ссылка на сумму, которая является основой ждя расчета пеней - повсему циклу дат
        self.end_date = datetime.strptime(end_date, "%Y.%m.%d").date()
        self.stavka_data = self.load_stavka_data()
        self.start_date = self.parse_start_date()


    # 01     Выгрузка ставок ЦБ РФ из файла (Пока планируется именно из файла, в дальнейшем - из файла и с сайта)
    def load_stavka_data(self):    # ........
        try:
            # Загружаем данные из Excel файла
            df = pd.read_excel(self.file_path, parse_dates=['Дата']) # колонка с названием "Дата" авт. конвертирована в формат даты сразу (тип datetime)
            # Преобразуем в словарь с датами как ключами
            return {row['Дата'].date(): row['Ставка'] for index, row in df.iterrows()}
        except FileNotFoundError:
            print("Ошибка1: файл ставки не найден.")
            return {}
        except Exception as e:
            print(f"Ошибка при загрузке данных: {e}")
            return {}

    # 02     ПРЕОБРАЗОВАНИЕ начальной ДАТЫ из периода типа "январь 2023"
    def parse_start_date(self):
        month = {
            "январь": "01.01",
            "февраль": "02.01",
            "март": "03.01",
            "апрель": "04.01",
            "май": "05.01",
            "июнь": "06.01",
            "июль": "07.01",
            "август": "08.01",
            "сентябрь": "09.01",
            "октябрь": "10.01",
            "ноябрь": "11.01",
            "декабрь": "12.01"
            }
        dolg_period = self.dolg_period.strip() # : это период вводимый пользователем формата: 'Январь 2024'
        a, b = dolg_period.split() # : разделяем на месяц и на год
        a = a.strip().lower() # : месяц
        b = b.strip() # : год
        if a in month:
            a = month[a].strip()
        start_date = f'{b}.{a}' # : итоговая строка вида даты
        start_date = datetime.strptime(start_date, "%Y.%m.%d").date() # приводим значение к формату даты 'datetime.datetime'(из строки)

        # Прибввляем один месяц к стартовой дате:
        start_date = start_date + relativedelta(months=1) # Дело в том, что долг за период, начало УЧЕТА расчетов запускается только со следующего месяца (ЭТО ПО ЖК РФ)

        # Сразу возвращаем значение в формате ДАТА и тип ДАТА 'datetime.date'
        return start_date

    # 03     ИЩЕМ СТАВКУ РЕФИНАНСИРОВАНИЯ ЦБ РФ на ДАТУ НАЧАЛА РАСЧЕТОВ
    # нужно найти значение ставки на ближайшую предыдущую дату, если на текущую ставка не установлена
    def current_stavka_CB_serch(self):
        start_date = self.start_date
        stavka_data = self.stavka_data

        # Если дата сразу есть в словаре, берем значение, если нет, то шагаем назад по-дням
        while start_date not in stavka_data:
                start_date -= timedelta(days=1)
        # Возвращаем результат (ищем пока не найдем)

        # Здесь мы присвоили начальную ставку, чтобы в расчетах не было нулевых значений ставки
        return stavka_data[start_date] # Все значение на дату получено
# --------------------------------------------------------------


#   03
#     КЛАСС отвечающий за реализацию основного кода программы:  Расчеты, получение таблиц результатов

class Process_data:
    #     Эти данные меняются только при изменении законодателтства (поэтому это атрибут самого класса)
    period_1 = Input_data.period_1  # Это законодательно, меняется вместе с законом. Поэтому определяем так.
    period_2 = Input_data.period_2  # Это законодательно, меняется вместе с законом.
    period_3 = Input_data.period_3  # Это законодательно.

    def __init__(self, end_date):
        fist = Prepare_data(end_date)
        self.start_date = fist.start_date # Начальная дата, с которой начинается отсчет всех расчетов, включая None и 0
        self.end_date = fist.end_date # Итоговая дата, на которую (до которой) мы производим все расчеты
        self.stavka_data = fist.stavka_data # Это таблица со ставками РФ СБ РФ (дата, ставка)
        self.dolg_sum = fist.dolg_sum # Сумма долга за 1 месяц

        initial = Input_data()
        #    моратрий определен указом Правительства - его можно будет только дополнять, если появится новый
        self.moratoryi_1 = initial.moratoryi_1
        self.moratoryi_2 = initial.moratoryi_2
        #   другие условия в calculate
        self.lok_stavka_CB = initial.lok_stavka_CB # Параметр определен законодательно,  можно и Атрибутам Класса Сделать
        self.st_300 = initial.st_300 # Параметр определен законодательно можно и Атрибутам Класса Сделать
        self.st_130 = initial.st_130 # Параметр определен законодательно  можно и Атрибутам Класса Сделать
        # ...
        self.current_stavka_CB = fist.current_stavka_CB_serch() # Расчитываем значение на начальную дату (иначе могут быть пустые значения)



    # 01     ОБРАБОТКА ДАТ по порядку расчета
    # Создаем построчный список (колонку) дат - основа для дальнейших обработок
    def date_range(self, start_date, end_date):    # ...
        start = start_date # Ничего не делаем, т.к. это уже <class 'datetime.date'
        end = end_date # Ничего не делаем, т.к. это уже <class 'datetime.date'

        current = start  # Инициализируем переменную текущей датой в цикле, который вызывает нас
        while current <= end:
            yield current
            current += timedelta(days=1)
    # --------------------------------------------------------------


    # 02 01    ОБРАБОТКА ДАТ МОРАТОРИЯ
    def moratorii_periods(self, moratoryi_1, moratoryi_2):
        # Объединяем периоды в общий список пар (в будущем может будет таблица таких периодов)
        date_para = [moratoryi_1, moratoryi_2]

        # Преобразуем строки в даты
        parsed_periods = []
        for start_date, end_date in date_para:
            parsed_periods.append([
                datetime.strptime(start_date, '%Y.%m.%d').date(),
                datetime.strptime(end_date, '%Y.%m.%d').date()
            ])
        return parsed_periods

    # 02 02     Принимает единственный параметр, чтобы определить - попадает он в мораторий или нет
    def is_date_in_moratoriy(self, single_date):
        for d_start, d_end in self.moratorii_periods(self.moratoryi_1, self.moratoryi_2):
            if d_start <= single_date <= d_end:
                return True
        return False
    # --------------------------------------------------------------


    # 03     РАСЧЕТ ПЕНЕЙ
       # Расчитываем значение начисленных пеней на каждую передаваемую дату
       # 1/300 от ставки рефинансирования ЦБ РФ  и   1/130 от ставки рефинансирования ЦБ РФ
    def calculate(self, flag_stavky, current_stavka_CB): # dolg_sum, current_stavka_CB, flag_stavky
        dolg = self.dolg_sum
        stavka_CB = current_stavka_CB
        st_300 = self.st_300
        st_130 = self.st_130

        notlok = stavka_CB # понадобится для информации в отчетах (это когда ставка выше ограничения)

        # Приводим значение ставки Рефинансирования под ограничение по законодательству РФ
        if stavka_CB > self.lok_stavka_CB:
            stavka_CB = self.lok_stavka_CB

        if flag_stavky == 1:
            deliel = st_300
        elif flag_stavky == 2:
            deliel = st_130
        else:
             deliel = 1 # Легко обходимся без этого действия, т.е. без  "elif", Но оставил для контроля расчетов.

        # Создаем перем. для возможности информировать получателя об ограничении
        lok = stavka_CB  # информирование (в расчетах не участвует)

        result = float((stavka_CB / 100) / deliel * dolg)  # Делаем число с плавающей точкой и округляем

        return result, lok, notlok
    # --------------------------------------------------------------


    # 04 РАСЧЕТ ПЕНЕЙ по ДНЯМ на каждую дату в периоде (список словарей)
    def raschet_on_list(self):

        # Объявление условий по применению ставок (делителей) к расчету пеней
        stop_date_10 = self.start_date + timedelta(days=Process_data.period_1) # ДатаНачала + 10 дней
        # print(stop_date_10)
        stop_date_30 = stop_date_10 + timedelta(days=Process_data.period_2) # ДатаНачала + 10 дней + 30 дней,   т.е. на 31-й
        # print(stop_date_30)
        stop_date_90 = stop_date_10 + timedelta(days=Process_data.period_3) # ДатаНачала + 10 дней + 90 дней   т.е. на 91-й
        # print(stop_date_90)
        current_stavka_CB = self.current_stavka_CB
        flag_stavky = None

        results = []
        for single_date in self.date_range(self.start_date, self.end_date): # переборка дат между заданными датами
            # Пропуск дат, попадающих в периоды моратория
            if single_date in self.stavka_data:
                current_stavka_CB = self.stavka_data[single_date] # обновляем если есть изменения

            if self.is_date_in_moratoriy(single_date):
                results.append({
                    'Дата': single_date,
                    'Сумма': 0.0,  # Дата входит в мораторий, расчёт не производится
                    'Ставка к расчету': "  - ", #None
                    'Ставка ЦБ РФ': current_stavka_CB
                })
                continue

            if current_stavka_CB is not None:
                if single_date < stop_date_10:
                    result, lok, notlok = self.calculate(flag_stavky, current_stavka_CB)
                    result = 0
                elif single_date < stop_date_30:
                    result, lok, notlok = self.calculate(flag_stavky, current_stavka_CB)
                    result = float(0)
                elif single_date < stop_date_90:
                    flag_stavky = 1
                    result, lok, notlok = self.calculate(flag_stavky, current_stavka_CB)
                    result = float(result)
                else:
                    flag_stavky = 2
                    result, lok, notlok = self.calculate(flag_stavky, current_stavka_CB)
                    result = float(result)

                # Добавляем в список словарь (список словарей)
                results.append({
                    'Дата': single_date,
                    'Сумма': result,
                    'Ставка к расчету': lok,
                    'Ставка ЦБ РФ': notlok
                })
                # print(type(single_date))

            else:
                result = 0
                results.append({
                    'Дата': single_date,
                    'Сумма': 'Что за Ошибка?', #result,  #  "Ставка не найдена."
                    'Ставка к расчету': None,
                    'Ставка ЦБ РФ': None
                })
        return results

    # --------------------------------------------------------------


class Reports_1:
    # ПЕРВАЯ по дням (форма 1)
    def __init__(self, end_date):
        self.second = Process_data(end_date) # с  self. - потому что реализация идет из метода


    def output_1(self):

        # Переменная для заголовков
        header = f"{'Дата':^12} {'Результат':<8}  {'Ставка к расчету':>16}  {'Ставка ЦБ РФ':>16}"
        print(header)
        print("-" * len(header))


        total_result = 0  # Общая сумма
        monthly_result = 0  # Сумма за текущий месяц
        current_month = None  # Переменная для хранения текущего месяца
        for i in self.second.raschet_on_list(): # Распаковываем список словарей
            single_date, result, lok, notlok = i.values() # Распаковываем словарь (берем только значения)
            current_result = round(result, 3)

            # Суммируем результат
            total_result += current_result  # Обновляем итоговую сумму

            # Проверяем, изменился ли месяц
            if current_month is None:  # Если это первое значение
                current_month = single_date.month

            if single_date.month != current_month:  # Если месяц изменился
                mouns_print = single_date - relativedelta(months=1)
                mouns_print = mouns_print.strftime('%B %Y')
                print(f'{mouns_print}:   {round(monthly_result, 2)} руб.')
                monthly_result = 0  # Сбрасываем сумму за месяц
                current_month = single_date.month  # Обновляем текущий месяц

            # Добавляем результат в сумму за месяц
            monthly_result += current_result

            # Выводим информацию по дате
            print(f"{single_date.strftime('%Y.%m.%d')}   {round(result, 2)} руб. {type(result)}     {lok} % {type(lok)}              {notlok} %   ")

        # Выводим итоговые результаты после завершения цикла
        if monthly_result > 0:  # Если есть сумма за последний месяц, выводим её
            print(f'{mouns_print}:   {round(monthly_result, 2)} руб.')

        print(f'Общий результат: {round(total_result, 2)} руб.')
 # --------------------------------------------------------------

class Reports_2:
    # МИН и МАХ ДАТЫ ПО МЕСЯЦАМ ЗА ПЕРИОД 3
    # все работает корректно, оптимизирована циклическая переборка - сокращено количество строк исполняемого кода

    def __init__(self, end_date):
        self.second = Process_data(end_date) # с  self. - потому что реализация идет из метода
        self.start_date = self.second.start_date
        self.end_date = self.second.end_date
        self.result_one = self.get_monthly_min_max()


    #   01 Получаем все периоды по месяцам для группировки
    # Получаем первое число рассматриваемого месяца начала расчетов (Первое!)
    def get_month_start(self, year, month):
        return date(year, month, 1)
    # Получаем последнее число рассматриваемого месяца окончания расчетов (Именно Последнее число!)
    def get_month_end(self, year, month):
        if month == 12:
            return date(year + 1, 1, 1) - timedelta(days=1)
        else:
            return date(year, month + 1, 1) - timedelta(days=1)

    def get_monthly_min_max(self):
        start_date = self.start_date
        end_date = self.end_date
        result = {}
        year, month = start_date.year, start_date.month
        while (year, month) <= (end_date.year, end_date.month):
            min_date = max(start_date, self.get_month_start(year, month))
            max_date = min(end_date, self.get_month_end(year, month))
            result[(year, month)] = {"min": min_date, "max": max_date}
            # переход к следующему месяцу
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
        return result
   # ---------------------------

    def report_1(self):
        monthly_sums = {}
        raschet_on_list = self.second.raschet_on_list()

        for (year, month), dates  in self.result_one.items():
            min_date = dates['min']
            max_date = dates['max']

            # Проходим по результатам расчетов
            for i in raschet_on_list: # Распаковываем список словарей
                single_date, result, lok, notlok = i.values() # Распаковываем словарь (берем только значения)
                if min_date <= single_date <= max_date:
                    # Увеличиваем сумму для соответствующего года и месяца
                    month_key = (year, month)
                    if month_key not in monthly_sums:
                        monthly_sums[month_key] = float(0)  # Инициализация суммы, если ее еще нет

                    monthly_sums[month_key] += float(result)  # Добавляем результат к сумме
                    # Округляем текущее значение после добавления
                    monthly_sums[month_key] = round(monthly_sums[month_key], 2)

        return monthly_sums  # Возвращаем новый словарь с суммами

 # --------------------------------------------------------------

class Reports_mane:
    pass

# --------------------------------------------------------------

# 00 01         ВВОДНЫЕ ДАННЫЕ (те что вводим каждую загрузку)

dolg_period_pass = None # будет загружаться файл

# Конечная дата по которую нужно расчитать пени
end_date = '2023.11.30'   # Конечная дата рассматриваемого периода, будет вводиться пользователем
# end_date = datetime.strptime(end_date, "%Y.%m.%d").date() # Приводим значение Введенное Пользователем в формат datetime

# ЗАПУСК НА РЕЗУЛЬТАТ
fist = Prepare_data(end_date)
second = Process_data(end_date)


# print('------ Пробник 1 ------\n')
# for i, j in fist.load_stavka_data().items():
#     print(i, j, type(i)) #type(i)

# print('------ Пробник 2 ------\n')
# result = fist.parse_start_date()
# # print(fist.dolg_sum)
# print(fist.dolg_sum, result, type(result),'\n')

# print('------ Пробник 3 ------\n')
# print(fist.end_date, type(fist.end_date),'\n')

# print('------ Пробник 4 ------\n')
# print(fist.current_stavka_CB_serch(),'\n')
# print(second.current_stavka_CB,'\n')


print('------ Пробник 5 ------\n')
third = Reports_1(end_date)
third.output_1()
# print(second.period_1)


print('------ Пробник 6 ------\n')
reports_two = Reports_2(end_date)
result = reports_two.get_monthly_min_max()


# Вывод результатов
# for (year, month), (dates)  in result.items():
#     min2 = dates['min']
#     max2 = dates['max']
#     print(f'{(year, month)}:   Min: {min2} - Max: {max2} ({type(max2)})')

result_2 = reports_two.report_1()
# Вывод результатов
for (year, month), (summa)  in result_2.items():
    print(f'{(year, month)}:  - {round(summa, 6)} ({type(summa)})')

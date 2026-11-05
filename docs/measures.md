# Меры DAX и модель

## Модель

```
DimDate[date] 1 ──── * VMT[month]      (однонаправленная связь)
DimState[state] 1 ─── * VMT[state]     (однонаправленная связь)
```

- `VMT` — таблица факта, режим Import, источник `data/traffic_vmt_monthly.csv`.
- `DimDate` — календарь на каждый день, режим Import, источник `data/dim_date.csv`.
- `DimState` — справочник штатов и регионов FHWA, источник `data/dim_state.csv`.
- Параметр `DataBase` — папка с CSV. По умолчанию указывает на публичный
  URL репозитория; для локальной работы поставьте путь к папке `data`.

Power Query: каждый источник читается как `Csv.Document` в UTF-8 с
последующим `Table.PromoteHeaders` и явным приведением типов
(`month → date`, `vmt_millions → number`, `stations → Int64`).

## Меры

| Мера | DAX | Зачем |
|---|---|---|
| `Total VMT` | `SUM ( VMT[vmt_millions] )` | Базовый объём в текущем фильтре |
| `VMT L12M` | окно `DATESINPERIOD` на 12 месяцев от `MAX ( VMT[month] )`; `BLANK()`, если в окне меньше 12 месяцев с данными | Последние 12 месяцев от последнего месяца с данными, а не от конца календаря |
| `VMT Prev12M` | то же окно на 24 месяца минус `[VMT L12M]`; `BLANK()`, если данных меньше 24 месяцев | Предыдущие 12 месяцев |
| `VMT YoY %` | `DIVIDE ( [VMT L12M] - [VMT Prev12M], [VMT Prev12M] )` | Сравнение двух полных окон; на карточке «Обзор» |
| `VMT LY` | `CALCULATE ( [Total VMT], SAMEPERIODLASTYEAR ( DimDate[date] ) )` | Тот же месяц год назад |
| `VMT YoY Month %` | `DIVIDE ( [Total VMT] - [VMT LY], [VMT LY] )` | Месяц к тому же месяцу прошлого года; линия на «Динамике» |
| `Avg Monthly VMT` | `AVERAGEX ( VALUES ( DimDate[date] ), [Total VMT] )` | Средний месяц в фильтре |
| `States Reporting` | `DISTINCTCOUNT ( VMT[state] )` | Покрытие: сколько штатов вернуло данные |
| `VMT Share` | `DIVIDE ( [Total VMT], CALCULATE ( [Total VMT], ALLSELECTED ( DimState ) ) )` | Доля штата в выбранных регионах |
| `VMT Top10` | `RANKX ( ALLSELECTED ( DimState[state] ), [Total VMT] )`; значение возвращается только для первых десяти штатов | Ровно 10 штатов в рейтинге, без прокрутки |

`VMT Seasonality` и `Monitoring Stations` (сумма `stations`) описаны в модели
как вспомогательные; в отчёт они не выведены, чтобы не создавать ложного
впечатления, что число постов учёта равно интенсивности.

Неполные окна дают `BLANK()`, поэтому линия «Скользящее окно 12 месяцев»
начинается только там, где наблюдений действительно хватает на полный год.

## Почему год к году считается двумя окнами

Календарь длиннее факта, а 2026 год неполный. Если брать `SAMEPERIODLASTYEAR`
от максимума календаря, окно захватывает месяцы без данных и занижает итог.
Поэтому `VMT L12M`/`VMT Prev12M` отсчитываются от `MAX ( VMT[month] )` —
последнего месяца, за который есть наблюдения.

## Проверка

`scripts/verify_kpis.py` пересчитывает те же величины по CSV без pandas и DAX
и пишет `reports/kpi_check.md`. Совпадение с карточками отчёта:
3 331 842 млн за 12 месяцев и +0,6% год к году.

# Файл: src/reports/excel_exporter.py
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


class ExcelExporter:
    """Модуль генерации стабильных отчетов бюджетов неопределенности в Excel"""

    @staticmethod
    def export_emc_budget(output_dir: str, task_name: str, method_name: str,
                          freq_range_str: str, budget_data: list):
        """Создает форматированную таблицу Excel с безопасными формулами RSS без сбоев XML"""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "EMC Uncertainty Budget"

        # Гарантируем отображение сетки таблицы
        ws.views.sheetView[0].showGridLines = True

        # Метрологические шрифты и заливки
        font_title = Font(name="Arial", size=12, bold=True)
        font_header = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        font_bold = Font(name="Arial", size=10, bold=True)
        font_regular = Font(name="Arial", size=10)

        fill_header = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        fill_summary = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

        border_thin = Side(border_style="thin", color="000000")
        box_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

        # 1. Заголовки отчета
        ws.append([f"Инструментальный бюджет неопределенности: {method_name}"])
        ws.append([f"Исследуемый диапазон частот: {freq_range_str}"])
        ws.cell(row=1, column=1).font = font_title
        ws.cell(row=2, column=1).font = font_regular
        ws.append([])  # Пустой разделитель

        # 2. Шапка таблицы
        headers = [
            "Источник неопределенности (Составляющая)",
            "Измерительное оборудование / Модель",
            "Исходное значение [дБ]",
            "Закон распределения (k)",
            "Стандартная неопределенность u(xi) [дБ]"
        ]
        ws.append(headers)
        header_row_idx = 4

        for col_idx in range(1, 6):
            cell = ws.cell(row=header_row_idx, column=col_idx)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = box_border

        # 3. Заполнение данными измерительных приборов
        start_data_row = 5
        for item in budget_data:
            ws.append([
                item['name'],
                item['device'],
                item['raw_val'],
                item['dist'],
                item['u_std']
            ])
            current_row = ws.max_row
            for col_idx in range(1, 6):
                c = ws.cell(row=current_row, column=col_idx)
                c.font = font_regular
                c.border = box_border
                c.alignment = align_center if col_idx > 2 else align_left

        end_data_row = ws.max_row

        # 4. 💡 ПОСТРОЕНИЕ БЕЗОПАСНЫХ ЖИВЫХ ФОРМУЛ RSS
        # Вместо SUMSQ генерируем строку вида: =SQRT(E5^2+E6^2) — это на 100% стабильно для XML
        formula_parts = [f"E{r}^2" for r in range(start_data_row, end_data_row + 1)]
        rss_formula = f"=SQRT({'+'.join(formula_parts)})"

        comb_row = end_data_row + 1
        exp_row = end_data_row + 2

        # Записываем данные в ячейку ДО объединения, чтобы текст не пропадал
        ws.cell(row=comb_row, column=1, value="=== СУММАРНАЯ СТАНДАРТНАЯ НЕОПРЕДЕЛЕННОСТЬ ===")
        ws.cell(row=comb_row, column=4, value="k = 1")
        ws.cell(row=comb_row, column=5, value=rss_formula)

        ws.cell(row=exp_row, column=1, value="=== РАСШИРЕННАЯ НЕОПРЕДЕЛЕННОСТЬ ЛАБОРАТОРИИ (U_lab) ===")
        ws.cell(row=exp_row, column=4, value="NORMAL (k = 2, 95%)")
        ws.cell(row=exp_row, column=5, value=f"=E{comb_row}*2")

        # 5. Красивое объединение, заливка и рамки ячеек подвала
        for r_idx in [comb_row, exp_row]:
            # Объединяем ячейки под текст
            ws.merge_cells(start_row=r_idx, start_column=1, end_row=r_idx, end_column=3)

            for col_idx in range(1, 6):
                cell = ws.cell(row=r_idx, column=col_idx)
                cell.font = font_bold
                cell.fill = fill_summary
                cell.border = box_border
                cell.alignment = align_center if col_idx > 3 else align_left

                # Автоматическая подгонка ширины столбцов под длину текста
                for col in ws.columns:
                    max_len = 0
                    for cell in col:
                        # 💡 ИСПРАВЛЕНИЕ: Игнорируем объединенные ячейки (1, 2, 3 колонки) строк подвала,
                        # чтобы таблица не разъезжалась вширь из-за длинных названий суммарных неопределенностей
                        if cell.row in [comb_row, exp_row] and cell.column in [1, 2, 3]:
                            continue
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))

                    col_letter = openpyxl.utils.get_column_letter(col[0].column)
                    ws.column_dimensions[col_letter].width = max(max_len + 3, 15)

                # Жестко задаем оптимальную ширину первой и второй колонок под названия ГОСТа и приборов
                ws.column_dimensions['A'].width = 45
                ws.column_dimensions['B'].width = 45

                # Сохранение итоговой книги
                file_path = os.path.join(output_dir, f"Uncertainty_Budget_{task_name}.xlsx")
                wb.save(file_path)

class TableProfile:
    def __init__(self, name: str, row_count: int, null_count: int, column_count: int):
        self.name = name
        self.row_count = row_count
        self.null_count = null_count
        self.column_count = column_count
        self.null_pct = self._calculate_null_pct()

    def _calculate_null_pct(self) -> float:
        """
        :return: % of null fields
        """
        try:
            return round((self.null_count / (self.row_count*self.column_count)) * 100,2)
        except ZeroDivisionError:
            return 0.0
        except TypeError as e:
            print(f"Invalid input type: {e}")
            return 0.0

    def get_status(self) -> str:
        """
        :param null_percentage:
        :return: 'critical' if above 10%, 'warning' if above 5%, otherwise 'ok'
        """
        if self.null_pct > 10:
            status = "critical"
        elif self.null_pct > 5:
            status = "warning"
        else:
            status = "ok"

        return status

    def __str__(self):
        status = self.get_status()
        return(f'Table "{self.name}" | Rows: {self.row_count} | Columns: {self.column_count} | Null %: {self.null_pct} | Status: {status}')

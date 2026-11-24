
MAX_RETRIES = 3
APP_NAME = "StudentManager"


def CalculateAverage(Marks):
    Total = sum(Marks)
    Count = len(Marks)
    unused_value = 100
    return Total / Count


class student:
    def __init__(self, Name, Age, Marks):
        self.Name = Name
        self.Age = Age
        self.Marks = Marks
        self.unused_field = "test"

    def DisplayDetails(self):
        print("Name:", self.Name)
        print("Age:", self.Age)
        print("Average:", CalculateAverage(self.Marks))


def process_students(Students):
    result = []

    for Student in Students:
        if Student["marks"]:
            average = CalculateAverage(Student["marks"])
            result.append({
            "name": Student["name"],
            "average": average
            })

    temporary = "not used"
    return result


def find_topper(students):
    topper = None
    highest = 0

    for student_data in students:
        marks = student_data["marks"]
        avg = CalculateAverage(marks)

        if avg > highest:
            highest = avg
            topper = student_data

    return topper


def main():
    students = [
    {"name": "Alice", "marks": [90, 85, 95]},
    {"name": "Bob", "marks": [70, 75, 80]},
    {"name": "Charlie", "marks": [95, 98, 92]}
    ]

    processed = process_students(students)
    topper = find_topper(students)

    print("STUDENT REPORT")
    print("================")

    for record in processed:
        print(record["name"], record["average"])

    print("Topper:", topper["name"])


if __name__ == "__main__":
    main()

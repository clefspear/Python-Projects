class Restaurant():
     number_served = 0;
     def __init__(self,name,cuisine):
          self.name = name
          self.cuisine = cuisine
     def describe_restaurant(self):
          print(self.name.title() + " is the best fucking restaurant ever and the " + self.cuisine.title() + " tastes Grrrrrrrrreat.\n\n")
     def open_restaurant(self):
          print(self.name.title() + " is OPEN, Jackass!\n\n\n")
r1 = Restaurant('tittytwister','chinese')
#r2 = Restaurant('taffylaughyhappy','italian')
#r3 = Restaurant('drpeppertown', 'indian')

print("\nThe newly found restaurant, " + r1.name.title() + " serves the best goddamn " + r1.cuisine.title() + " in the fucking solar system.\n")
r1.describe_restaurant()
r1.open_restaurant()

class User():
     def __init__(self,first_name,last_name,age):
          self.first_name = first_name
          self.last_name = last_name
          self.age = age
     def describe_user(self):
          print(self.first_name.title() +" " + self.last_name.title() + " | Age:",int(self.age), "\n")
     def greet_user(self):
          print("\nYou aren't a piece of shit! okay " + self.first_name.title() + "?\n\n")

u1 =User("Peter","Azmy",22)


print("\nThis piece of shit, " + u1.first_name.title() +" " + u1.last_name.title() + " is so fucking old he's" ,int(u1.age), "in the fucking solar system.\n")
u1.describe_user()
u1.greet_user()
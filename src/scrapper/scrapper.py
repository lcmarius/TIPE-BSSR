from src.objects.bike import Bike
from src.objects.station import Station
from src.scrapper.api import API, get_bikes, get_stations
from src.scrapper.database import Database


def register_bikes(api: API, database: Database) -> None:
    bikes_data = get_bikes(api)
    bikes = []
    for bike_data in bikes_data:
        velo = Bike(
            bike_id=bike_data['id'],
            number=bike_data['number'],
            status=bike_data['status']
        )
        bikes.append(velo)
    database.upsert_bikes(bikes)

def register_stations(api: API, database: Database) -> None:
    stations_data = get_stations(api)
    stations=[]
    for station_data in stations_data:
        station = Station(
            station_number=int(station_data['number']),
            name=station_data['name'],
            capacity=station_data['totalStands']['capacity'],
            address=station_data.get('address'),
            geo_long=station_data['position']['longitude'],
            geo_lat=station_data['position']['latitude'],
            connected=station_data['connected']
        )

        stations.append(station)
    database.upsert_stations(stations)



def run():
    api= API()
    database=Database("/home/marius/PycharmProjects/TIPE-BSSR/data/scrapper.sql", True)

    register_stations(api, database)
    register_bikes(api, database)

    database.close()

if __name__ == "__main__":
    print("Lancement du scrapper...")
    run()
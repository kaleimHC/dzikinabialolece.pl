import random
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone
from datetime import timedelta
from sightings.models import Sighting, GridCell


class Command(BaseCommand):
    help = "Generate test GridCells and Sightings for Bialoleka"

    def handle(self, *args, **options):
        # Bialoleka bounds
        LON_MIN, LON_MAX = 20.95, 21.08
        LAT_MIN, LAT_MAX = 52.28, 52.38
        CELL_SIZE = 0.01  # ~1km

        # Clear existing test data
        GridCell.objects.all().delete()
        Sighting.objects.all().delete()
        self.stdout.write("Cleared existing data")

        # Generate grid cells
        cells = []
        cell_id = 0
        lon = LON_MIN
        while lon < LON_MAX:
            lat = LAT_MIN
            while lat < LAT_MAX:
                cell_id += 1
                polygon = Polygon(
                    [
                        (lon, lat),
                        (lon + CELL_SIZE, lat),
                        (lon + CELL_SIZE, lat + CELL_SIZE),
                        (lon, lat + CELL_SIZE),
                        (lon, lat),
                    ]
                )
                centroid = Point(lon + CELL_SIZE / 2, lat + CELL_SIZE / 2)
                cell = GridCell(
                    grid_id=f"GRID_{cell_id:04d}",
                    geometry=polygon,
                    centroid=centroid,
                    district="Bialoleka",
                    sighting_count=0,
                )
                cells.append(cell)
                lat += CELL_SIZE
            lon += CELL_SIZE

        GridCell.objects.bulk_create(cells)
        self.stdout.write(f"Created {len(cells)} grid cells")

        # Generate sightings
        all_cells = list(GridCell.objects.all())
        sightings = []
        now = timezone.now()

        for i in range(500):
            cell = random.choice(all_cells)
            # Random point within cell
            bounds = cell.geometry.extent  # (xmin, ymin, xmax, ymax)
            lon = random.uniform(bounds[0], bounds[2])
            lat = random.uniform(bounds[1], bounds[3])

            sighting = Sighting(
                location=Point(lon, lat),
                observed_at=now - timedelta(days=random.randint(0, 30)),
                status="verified",
                boar_count=random.choice(["1", "2-3", "4-10", "10+"]),
                sighting_type=random.choice(["encounter", "ryjowisko"]),
                description=f"Test sighting {i + 1}",
                grid_cell=cell,
            )
            sightings.append(sighting)
            cell.sighting_count += 1

        Sighting.objects.bulk_create(sightings)

        # Update cell counts
        for cell in all_cells:
            cell.save()

        self.stdout.write(self.style.SUCCESS(f"Created {len(sightings)} sightings"))
        self.stdout.write(self.style.SUCCESS("Done!"))

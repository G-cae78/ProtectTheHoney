import { Button } from "@/components/ui/button";
import avatar from "@/assets/avatar.jpg";
import darkKnight from "@/assets/darkKnight.jpg";
import inception from "@/assets/inception.jpg";
import matrix from "@/assets/matrix.jpg";

const movies = [
  //{ name: "Inception", price: "$3.99", image: inception, description: "A mind-bending thriller by Christopher Nolan.", size: "HD" },
  { name: "The Matrix", price: "$2.99", image: matrix, description: "A sci-fi classic that redefined the genre.", size: "HD" },
  { name: "Avatar", price: "$4.99", image: avatar, description: "An epic journey through space and time.", size: "4K" },
  { name: "The Dark Knight", price: "$3.49", image: darkKnight, description: "The legend of Batman continues.", size: "4K" },
];

const Products = () => {
  return (
    <section className="py-20 bg-gradient-to-b from-muted/30 to-background">
      <div className="container mx-auto px-4">
        <h2 className="text-5xl font-bold mb-12 text-center text-foreground">
          Our Movie Collection
        </h2>

        <div className="grid md:grid-cols-3 gap-10">
          {movies.map((movie, i) => (
            <div
              key={i}
              className="bg-card rounded-3xl overflow-hidden shadow-lg hover:shadow-xl transition-transform hover:scale-[1.03]"
            >
              <div className="relative h-80 w-full overflow-hidden">
                <img
                  src={movie.image}
                  alt={movie.name}
                  className="w-full h-full object-cover"
                />
              </div>

              <div className="p-6 text-center">
                <h3 className="text-2xl font-bold mb-2 text-foreground">
                  {movie.name}
                </h3>
                <p className="text-muted-foreground mb-2">{movie.size}</p>
                <p className="text-sm mb-4 text-muted-foreground">
                  {movie.description}
                </p>
                <Button className="w-full">{movie.price} • Watch Now</Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Products;

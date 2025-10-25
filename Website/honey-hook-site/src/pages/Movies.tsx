import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import avatar from "@/assets/avatar.jpg";
import darkKnight from "@/assets/darkKnight.jpg";
import inception from "@/assets/inception.jpg";
import matrix from "@/assets/matrix.jpg";

const movieList = [
  {
    id: 1,
    title: "Inception",
    img: inception,
    description: "A mind-bending thriller by Christopher Nolan.",
  },
  {
    id: 2,
    title: "The Matrix",
    img: matrix,
    description: "A sci-fi classic that redefined the genre.",
  },
  {
    id: 3,
    title: "Interstellar",
    img: "https://m.media-amazon.com/images/I/91kFYg4fX3L._AC_SY679_.jpg",
    description: "An epic journey through space and time.",
  },
  {
    id: 4,
    title: "The Dark Knight",
    img: darkKnight,
    description: "The legend of Batman continues.",
  },
  {
    id: 5,
    title: "Avatar",
    img: avatar,
    description: "A visually stunning sci-fi masterpiece.",
  },
];

const Movies = () => {
  const navigate = useNavigate();

  const openMovie = (movieId: number) => {
    navigate(`/movies/${movieId}`);
  };

  return (
    <>
      <Navbar />
      <section className="pt-24 pb-20 bg-gradient-to-b from-muted/30 to-background min-h-screen">
        <div className="container mx-auto px-4">
          <h1 className="text-5xl font-bold mb-12 text-center text-foreground">
            Browse Our Movie Collection
          </h1>

          <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">
            {movieList.map((movie) => (
              <div
                key={movie.id}
                onClick={() => openMovie(movie.id)}
                className="cursor-pointer group bg-card rounded-2xl overflow-hidden shadow-lg hover:scale-105 transition-transform duration-300"
              >
                <div className="h-80 w-full overflow-hidden">
                  <img
                    src={movie.img}
                    alt={movie.title}
                    className="w-full h-full object-cover group-hover:opacity-80 transition"
                  />
                </div>
                <div className="p-4">
                  <h2 className="text-xl font-bold text-foreground mb-2">
                    {movie.title}
                  </h2>
                  <p className="text-muted-foreground text-sm line-clamp-2">
                    {movie.description}
                  </p>
                  <Button className="w-full mt-4">Watch Now</Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
};

export default Movies;

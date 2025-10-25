import { useParams, useNavigate } from "react-router-dom";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import avatar from "@/assets/avatar.jpg";
import darkKnight from "@/assets/darkKnight.jpg";
import inception from "@/assets/inception.jpg";
import matrix from "@/assets/matrix.jpg";

const movieData = {
  1: {
    title: "Inception",
    description: "A mind-bending thriller by Christopher Nolan.",
    img: inception,
    trailer: "https://www.youtube.com/watch?v=YoHD9XEInc0",
  },
  2: {
    title: "The Matrix",
    description: "A sci-fi classic that redefined the genre.",
    img: matrix,
    trailer: "https://www.youtube.com/watch?v=vKQi3bBA1y8",
  },
  3: {
    title: "Interstellar",
    description: "An epic journey through space and time.",
    img: "https://m.media-amazon.com/images/I/91kFYg4fX3L._AC_SY679_.jpg",
    trailer: "https://www.youtube.com/watch?v=zSWdZVtXT7E",
  },
  4: {
    title: "The Dark Knight",
    description: "The legend of Batman continues.",
    img: darkKnight,
    trailer: "https://www.youtube.com/watch?v=EXeTwQWrcwY",
  },
  5: {
    title: "Avatar",
    description: "A visually stunning sci-fi masterpiece.",
    img: avatar,
    trailer: "https://www.youtube.com/watch?v=5PSNL1qE6VY",
  },
};

const MovieDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const movie = movieData[Number(id) as keyof typeof movieData];

  if (!movie) {
    return <div className="p-10 text-center text-2xl">Movie not found.</div>;
  }

  return (
    <>
      <Navbar />
      <section className="pt-24 pb-20 container mx-auto px-4">
        <div className="flex flex-col md:flex-row gap-8 items-start">
          <img
            src={movie.img}
            alt={movie.title}
            className="w-full md:w-1/3 rounded-3xl shadow-lg"
          />
          <div className="flex-1">
            <h1 className="text-5xl font-bold mb-4">{movie.title}</h1>
            <p className="text-lg text-muted-foreground mb-6">
              {movie.description}
            </p>
            <Button
              onClick={() => window.open(movie.trailer, "_blank")}
              className="mr-4"
            >
              Watch Trailer
            </Button>
            <Button variant="outline" onClick={() => navigate(-1)}>
              Back
            </Button>
          </div>
        </div>
      </section>
    </>
  );
};

export default MovieDetail;

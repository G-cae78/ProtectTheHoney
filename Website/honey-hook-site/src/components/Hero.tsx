import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import heroImage from "@/assets/hero-movie.jpg";

const Hero = () => {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <div
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `url(${heroImage})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-background/95 via-background/80 to-transparent" />
      </div>

      <div className="container mx-auto px-4 z-10">
        <div className="max-w-2xl">
          <h1 className="text-6xl font-bold mb-6 text-foreground">
            Stream Your Favorite{" "}
            <span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
              Movies Anytime
            </span>
          </h1>
          <p className="text-xl text-muted-foreground mb-8">
            Discover the latest blockbusters, timeless classics, and exclusive content.
          </p>

          <div className="flex gap-4">
            <Link to="/movies">
              <Button size="lg" className="rounded-full px-8">
                Start Watching
              </Button>
            </Link>
            <Button size="lg" variant="outline" className="rounded-full px-8">
              Learn More
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;

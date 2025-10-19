import { Button } from "@/components/ui/button";
import heroImage from "@/assets/hero-honey.jpg";

const Hero = () => {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <div 
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `url(${heroImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-background/95 via-background/80 to-transparent" />
      </div>
      
      <div className="container mx-auto px-4 z-10">
        <div className="max-w-2xl">
          <h1 className="text-5xl md:text-7xl font-bold mb-6 text-foreground leading-tight">
            Pure, Natural
            <span className="block bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
              Golden Honey
            </span>
          </h1>
          <p className="text-xl md:text-2xl text-muted-foreground mb-8 leading-relaxed">
            Experience the authentic taste of nature's sweetest gift. Harvested with care, delivered with love.
          </p>
          <div className="flex flex-col sm:flex-row gap-4">
            <Button 
              size="lg" 
              className="text-lg px-8 py-6 rounded-full shadow-[var(--shadow-soft)] hover:scale-105 transition-transform"
            >
              Shop Now
            </Button>
            <Button 
              size="lg" 
              variant="outline"
              className="text-lg px-8 py-6 rounded-full border-2 hover:bg-accent/10 transition-[var(--transition-smooth)]"
            >
              Learn More
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;

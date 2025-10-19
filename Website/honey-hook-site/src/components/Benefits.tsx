import { Sparkles, Heart, Leaf } from "lucide-react";

const benefits = [
  {
    icon: Sparkles,
    title: "100% Pure",
    description: "No additives, no processing. Just pure, raw honey straight from the hive.",
  },
  {
    icon: Heart,
    title: "Health Benefits",
    description: "Rich in antioxidants and nutrients that support your overall wellness.",
  },
  {
    icon: Leaf,
    title: "Sustainably Sourced",
    description: "We care for our bees and the environment with ethical beekeeping practices.",
  },
];

const Benefits = () => {
  return (
    <section className="py-20 bg-gradient-to-b from-background to-muted/30">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4 text-foreground">
            Why Choose Our Honey?
          </h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Every jar tells a story of dedication, purity, and the natural sweetness of life.
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {benefits.map((benefit, index) => (
            <div
              key={index}
              className="bg-card p-8 rounded-3xl shadow-[var(--shadow-soft)] hover:scale-105 transition-transform duration-300"
            >
              <div className="w-16 h-16 bg-gradient-to-br from-primary to-secondary rounded-2xl flex items-center justify-center mb-6">
                <benefit.icon className="w-8 h-8 text-primary-foreground" />
              </div>
              <h3 className="text-2xl font-bold mb-4 text-foreground">
                {benefit.title}
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                {benefit.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Benefits;

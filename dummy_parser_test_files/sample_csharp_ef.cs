
using System;
using Microsoft.EntityFrameworkCore;

namespace MyWebApp.Models
{
    public class Product { public int ProductId { get; set; } public string Name { get; set; } public Category Category { get; set; } public int CategoryId {get;set;} }
    public class Category { public int CategoryId { get; set; } public string CategoryName { get; set; } public List<Product> Products { get; set; } }

    public class MyDbContext : DbContext
    {
        public DbSet<Product> Products { get; set; }
        public DbSet<Category> Categories { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder); // Example of other call

            modelBuilder.Entity<Product>()
                .HasKey(p => p.ProductId); // Single key
            
            modelBuilder.Entity<Product>()
                .Property(p => p.Name)
                .IsRequired()
                .HasMaxLength(100);

            modelBuilder.Entity<Category>()
                .Property(c => c.CategoryName).HasColumnName("CategoryTitle");

            // Relationship: Category has many Products
            modelBuilder.Entity<Category>()
                .HasMany(c => c.Products)
                .WithOne(p => p.Category)
                .HasForeignKey(p => p.CategoryId);
        }
    }
}
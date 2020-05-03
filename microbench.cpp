#include <iostream>
#include <stdlib.h>
#include <string.h>
#include <cstdint>

using namespace std;

void print_few(uint64_t * mem, int range)
{
  for (int i = 0; i < range; i++)
    cout << mem[i] << endl;
}

void get_param(int argc, char const* argv[], int* numitr, int* numvault)
{
  if (argc != 3) {
    cout << "Error: please pass in <num iter> <num vault>" << endl;
    exit(-1);
  }

  *numitr = atoi(argv[1]);
  *numvault = atoi(argv[2]);
}

int main(int argc, char const *argv[])
{
  // Setup
  int numitr, numvault;
  get_param(argc, argv, &numitr, &numvault);

  // Allocation
  int numElements = 33554432 * numvault; // 64-bit numbers are 8 bytes
  uint64_t* mem = (uint64_t*) malloc(sizeof(uint64_t) * numElements);

  // for (int i = 0; i < numElements; i++)
  //   mem[i] = (uint64_t) rand(); // Not intialize to 0 to bypass compiler optimization

  // Sanity check: print first 10 elements
  // print_few(mem, 10);

  // Microbench begin
  cout << "Microbench Start" << endl;
  int idxInVault = 0;
  int idxInHMC = 0;
  uint64_t val = 0;
  int i = 0;
  int idx = 0;
  while (i < numitr) {
    idxInVault = idx % 33554432;
    for (int j = 0; j < numvault; j++) {

      idxInHMC = idxInVault + 33554432*j;

      // Read from vault
      val = mem[idxInHMC];

      // Do some computation so that it doesn't get optimized out
      val += 1;

      // Store back to vault
      mem[idxInHMC] = val;

      i++;
    }
    idx++;
  }

  // Sanity check: make sure elements are now different
  // cout << "---------------------" << endl;
  // print_few(mem, 10);

  return 0;
}
